# NTIS 2024 official rpatent OpenAPI: title / technology / applicant discovery.
# Run only on the NTIS-approved Windows PC. PowerShell 5.1+.
# This collects RESEARCH LEADS: only identical KIPRIS APPLICATION numbers
# from RegistType=출원 / code=01 may enter records. No raw unrelated HITs.
param(
    [switch]$SelfTest,
    [switch]$OfflineTest,
    [string]$SnapshotRoot='',
    [ValidateRange(1,7)][int]$MaxTargets=7,
    [ValidateRange(1,21)][int]$MaxQueries=21,
    [ValidateRange(1,3)][int]$MaxPages=1
)
$ErrorActionPreference='Stop'
$api='https://www.ntis.go.kr/rndopen/openApi/public_result'
$raw='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/'
$outFile=Join-Path $PSScriptRoot 'ntis_patent_discovery_pc_latest.json'
$phase='INITIALIZE'
$profile='ntis_rpatent_2024_manual_keyword_discovery_v1'
if($OfflineTest){
    if(!$SnapshotRoot){throw 'OFFLINE_SNAPSHOT_ROOT_REQUIRED'}
    $outFile=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_patent_discovery_offline.json'
}

function Normalize-Patent([string]$value){
    if(!$value){return $null}
    $v=$value -replace '[\s-]',''
    if($v -match '^10\d{11}$'){return $v}
    return $null
}
function Clean-Text($node,[int]$limit){
    if($null -eq $node){return ''}
    $v=[regex]::Replace([string]$node.InnerText,'(?i)</?span\b[^>]*>','')
    $v=[regex]::Replace($v,'\s+',' ').Trim()
    if($v.Length -gt $limit){$v=$v.Substring(0,$limit)}
    return $v
}
function Read-OutcomeXml([string]$xml){
    if(!$xml -or $xml.Length -gt 1600000 -or $xml -match '(?i)<!DOCTYPE|<!ENTITY'){
        throw 'INVALID_OUTCOME_XML'
    }
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($xml)}catch{throw 'OUTCOME_XML_PARSE_FAILED'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'UNKNOWN_OUTCOME_RESPONSE'}
    $totalNode=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $totalNode -or $null -eq $set -or $totalNode.InnerText -notmatch '^\d{1,10}$'){
        throw 'UNKNOWN_OUTCOME_RESPONSE'
    }
    $hits=New-Object System.Collections.ArrayList
    foreach($hit in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
        $typ=$hit.SelectSingleNode('RegistType')
        [void]$hits.Add([pscustomobject]@{
            applicationOrRegistration=(Clean-Text ($hit.SelectSingleNode('RegistNumber')) 80)
            registType=(Clean-Text $typ 30)
            registTypeCode=if($null -ne $typ){[string]$typ.GetAttribute('code')}else{''}
            projectNumber=(Clean-Text ($hit.SelectSingleNode('ProjectID')) 40)
            outcomeId=(Clean-Text ($hit.SelectSingleNode('ResultID')) 100)
            outcomeTitle=(Clean-Text ($hit.SelectSingleNode('ResultTitle')) 200)
            projectTitle=(Clean-Text ($hit.SelectSingleNode('ProjectTitle')) 200)
            performingAgency=(Clean-Text ($hit.SelectSingleNode('PerformAgency')) 120)
        })
    }
    $total=[long]$totalNode.InnerText
    if($total -gt 0 -and $hits.Count -eq 0){throw 'OUTCOME_ROWS_UNRECOGNIZED'}
    return [pscustomobject]@{totalHits=$total;rows=@($hits.ToArray())}
}
function Get-Snapshot([string]$path){
    try{
        if($OfflineTest){
            $file=Join-Path $SnapshotRoot ($path -replace '/',[System.IO.Path]::DirectorySeparatorChar)
            return ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($file,[System.Text.Encoding]::UTF8))
        }
        $reply=Invoke-WebRequest -Uri ($raw+$path) -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
        if([int]$reply.StatusCode -ne 200 -or $reply.Content.Length -gt 2500000){throw 'bad_public_snapshot'}
        return ConvertFrom-Json -InputObject ([string]$reply.Content)
    }catch{throw 'PUBLIC_SNAPSHOT_DOWNLOAD_FAILED'}
}
function Candidate-Tech([string]$title){
    # Curated official KIPRIS title keywords, NOT a guessed ontology.
    # Prefer domain-specific compound terms over generic 도어 / 시스템 / 방법.
    $known=@('부분방전','상변태','침투탐상','메타렌즈','복합패널','방열 조성물','RTCM','고정자 냉각','배터리 열폭주','해중합','자율주행','전력설비')
    foreach($term in $known){if($title.Contains($term)){return $term}}
    $parts=@([regex]::Matches($title,'[가-힣A-Za-z0-9]{3,}') |
        ForEach-Object {$_.Value} | Where-Object {
            $_ -notin @('및','이를','포함하는','장치','방법','시스템','제어','차량','소자','제조방법','복합')
        } | Select-Object -First 2)
    if($parts.Count -gt 0){return ($parts -join ' ')}
    return $null
}
function Candidate-Title([string]$title){
    # A bounded literal fragment of official patent title; any indexing
    # mismatch will be explicitly reported, NOT treated as no R&D result.
    if(!$title){return $null}
    $v=[regex]::Replace($title,'\s+',' ').Trim()
    $v=$v -replace '\s+및\s+이.*$','' -replace '\s+및\s+그.*$',''
    if($v.Length -gt 42){$v=$v.Substring(0,42).Trim()}
    return $v
}
function Candidate-Applicant($applicants){
    # Use only corporate legal applicants, never private individuals.
    foreach($rawName in @($applicants)){
        $name=[string]$rawName
        if($name -notmatch '주식회사|\(주\)|㈜|산학협력단'){continue}
        $name=($name -replace '주식회사|\(주\)|㈜','').Trim()
        if($name.Length -lt 3 -or $name.Length -gt 45){continue}
        if($name -match '^\d+$'){continue}
        return $name
    }
    return $null
}
function Plan-Queries($dossier,$deep,[int]$maxTargets,[int]$maxQueries){
    $deepByPub=@{}
    foreach($row in @($deep.investigations)){
        $pub=Normalize-Patent ([string]$row.publicationNumber)
        $app=Normalize-Patent ([string]$row.applicationNumber)
        if(!$pub -or !$app){continue}
        if(!$deepByPub.ContainsKey($pub)){$deepByPub[$pub]=New-Object 'System.Collections.Generic.HashSet[string]'}
        [void]$deepByPub[$pub].Add($app)
    }
    $targets=New-Object System.Collections.ArrayList
    foreach($patent in @($dossier.dossiers)){
        $pub=Normalize-Patent ([string]$patent.publicationNumber)
        if(!$pub -or !$deepByPub.ContainsKey($pub) -or $deepByPub[$pub].Count -ne 1){continue}
        $source=@($deep.investigations | Where-Object {$_.publicationNumber -eq $pub} | Select-Object -First 1)
        $application=@($deepByPub[$pub])[0]
        $keyword=Candidate-Tech ([string]$patent.title)
        $phrase=Candidate-Title ([string]$patent.title)
        $applicant=if($source.Count){Candidate-Applicant $source[0].applicants}else{$null}
        [void]$targets.Add([pscustomobject]@{
            publicationNumber=$pub
            applicationNumber=$application
            technology=$keyword
            title=$phrase
            applicant=$applicant
        })
        if($targets.Count -ge $maxTargets){break}
    }
    $queryPlans=New-Object System.Collections.ArrayList
    # Round-robin spreads opportunities across firms instead of exhausting
    # all searches for one patent first.
    foreach($mode in @('technology','title','applicant')){
        foreach($t in @($targets.ToArray())){
            $q=[string]$t.$mode
            if($q.Length -lt 3 -or $q.Length -gt 70){continue}
            [void]$queryPlans.Add([pscustomobject]@{
                publicationNumber=$t.publicationNumber
                applicationNumber=$t.applicationNumber
                mode=$mode
                query=$q
            })
            if($queryPlans.Count -ge $maxQueries){return @($queryPlans.ToArray())}
        }
    }
    return @($queryPlans.ToArray())
}
function Query-Official([string]$term,[string]$key,[int]$startPosition,[int]$maxCount){
    if($OfflineTest){
        # Inject ONE matching application+project, ONE registration-type trap,
        # ONE unrelated patent to exercise the entire gate. Never claim live.
        $xml='<RESULT><TOTALHITS>3</TOTALHITS><RESULTSET>'+
        '<HIT><ResultID>TESTOUTCOME001</ResultID><RegistNumber>10-2025-0039383</RegistNumber><RegistType code="01">출원</RegistType><ProjectID>2410019058</ProjectID><ResultTitle>부분방전 센서</ResultTitle><ProjectTitle>전력설비 센서</ProjectTitle></HIT>'+
        '<HIT><ResultID>TESTREGISTER002</ResultID><RegistNumber>10-2025-0039383</RegistNumber><RegistType code="02">등록</RegistType><ProjectID>2410019058</ProjectID></HIT>'+
        '<HIT><ResultID>TESTOTHER003</ResultID><RegistNumber>10-2020-9999999</RegistNumber><RegistType code="01">출원</RegistType><ProjectID>2410019058</ProjectID></HIT>'+
        '</RESULTSET></RESULT>'
        return Read-OutcomeXml -xml $xml
    }
    if($term.Length -lt 3 -or $term.Length -gt 70){throw 'INVALID_SEARCH_TERM'}
    # Actual documented NTIS REST URI convention, collection=rpatent.
    # searchField is left empty: the official user PC's broad '부분방전'
    # probe returned live results in this mode. No undocumented applicant field.
    $params=[ordered]@{
        naviCount='30';searchField='';addQuery='DBT=PAT';query=$term
        displayCount=[string]$maxCount;sortby='';collection='rpatent'
        boostquery='';userId='';startPosition=[string]$startPosition
        apprvKey=$key;cmbnApiYn='Y'
    }
    $parts=@(foreach($p in $params.GetEnumerator()){
        [Uri]::EscapeDataString([string]$p.Key)+'='+[Uri]::EscapeDataString([string]$p.Value)
    })
    $url=$api+'?'+($parts -join '&')
    $code=$null;$body=$null
    try{
        $reply=Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        $code=[int]$reply.StatusCode;$body=[string]$reply.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$code=[int]$_.Exception.Response.StatusCode}catch{$code=$null}
        }
        if($null -eq $code){throw 'NTIS_NETWORK_OR_APPROVAL_ERROR'}
    }finally{$url=$null}
    if($code -ne 200){throw ('NTIS_HTTP_'+$code)}
    return Read-OutcomeXml -xml $body
}
if($SelfTest){
    $x=Read-OutcomeXml -xml '<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT><ResultID>X01001</ResultID><RegistNumber>10-2025-0039383</RegistNumber><RegistType code="01">출원</RegistType><ProjectID>2410019058</ProjectID></HIT></RESULTSET></RESULT>'
    if($x.rows.Count -ne 1 -or $x.rows[0].registTypeCode -ne '01' -or
       $x.rows[0].projectNumber -ne '2410019058'){throw 'OFFICIAL_OUTCOME_FIELDS_FAILED'}
    try{[void](Read-OutcomeXml -xml '<html>Access denied</html>');throw 'UNSAFE_HTML_PASSED'}
    catch{if($_.Exception.Message -ne 'UNKNOWN_OUTCOME_RESPONSE'){throw}}
    if((Candidate-Tech '케이블 부착식 부분방전 센서') -ne '부분방전'){throw 'TECH_PLAN_FAILED'}
    if((Candidate-Applicant @('민원기','엘에스전선 주식회사')) -ne '엘에스전선'){throw 'APPLICANT_PLAN_FAILED'}
    Write-Output 'PASS: official NTIS XML, technology/applicant query planning, HTML rejection'
    exit 0
}

Write-Output 'NTIS PATENT OUTCOME DISCOVERY - title / technology / corporate applicant'
Write-Output 'Keyword hits are NOT direct patent or national-project outcomes.'
$secret=$null;$key=$null
if($OfflineTest){
    Write-Output 'OFFLINE_TEST: only public snapshots and synthetic outcome rows, no key/network'
    $key='LOCAL_OFFLINE_ONLY'
}else{
    $phase='READ_KEY'
    $secret=Read-Host 'NTIS approved API key (hidden)' -AsSecureString
    $ptr=[IntPtr]::Zero
    try{
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}
}
try{
    $phase='READ_KIPRIS_DOSSIER'
    $dossier=Get-Snapshot 'digests/patent_rnd_dossiers_latest.json'
    $phase='READ_KIPRIS_DEEP'
    $deep=Get-Snapshot 'digests/patent_deep_latest.json'
    $phase='READ_NTIS_PROJECTS'
    $projects=Get-Snapshot 'digests/ntis_project_leads_latest.json'
    if($dossier.status -ne 'research_only' -or $projects.status -ne 'ready' -or
       $null -eq $dossier.dossiers -or $null -eq $deep.investigations -or
       $null -eq $projects.checks){throw 'INVALID_PUBLIC_SNAPSHOTS'}
    $projectIds=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach($check in @($projects.checks)){
        if($check.status -ne 'checked'){continue}
        foreach($p in @($check.records)){
            $projectNumber=[string]$p.projectNumber
            if($projectNumber -match '^\d{10}$'){[void]$projectIds.Add($projectNumber)}
        }
    }
    $phase='PLAN_QUERIES'
    $plans=@(Plan-Queries $dossier $deep $MaxTargets $MaxQueries)
    if(!$plans.Count){throw 'NO_KIPRIS_MATCHABLE_PATENTS'}
    $checks=New-Object System.Collections.ArrayList
    $matched=New-Object System.Collections.ArrayList
    $dedup=New-Object 'System.Collections.Generic.HashSet[string]'
    $errors=0;$observed=0;$sumHits=0
    $phase='EXECUTE_QUERIES'
    foreach($plan in $plans){
        $total=$null;$examined=0;$exact=0;$officialProj=0;$nPages=0
        $registrations=0;$unrelated=0;$hasProjectNotSample=0
        $errorCode=$null;$firstPageTruncated=$false
        try{
            for($page=0;$page -lt $MaxPages;$page++){
                $start=1+10*$page
                $r=Query-Official $plan.query $key $start 10
                if($null -eq $total){$total=$r.totalHits}
                $nPages++
                $examined+=@($r.rows).Count
                foreach($hit in @($r.rows)){
                    $app=Normalize-Patent $hit.applicationOrRegistration
                    if($hit.registType -ne '출원' -or $hit.registTypeCode -ne '01'){
                        $registrations++
                        continue
                    }
                    if($app -ne $plan.applicationNumber){
                        $unrelated++
                        continue
                    }
                    $exact++
                    if(!$projectIds.Contains([string]$hit.projectNumber)){
                        $hasProjectNotSample++
                        continue
                    }
                    if($hit.outcomeId -notmatch '^[A-Za-z0-9_-]{5,100}$'){continue}
                    $marker=$plan.publicationNumber+'|'+$hit.outcomeId+'|'+$hit.projectNumber
                    if(!$dedup.Add($marker)){continue}
                    [void]$matched.Add([pscustomobject]@{
                        publicationNumber=$plan.publicationNumber
                        patentApplicationNumber=$plan.applicationNumber
                        patentPublicationNumber=$null
                        projectNumber=$hit.projectNumber
                        sourceOfficialRecordId=$hit.outcomeId
                        sourceFieldMappingVerified=$true
                        registType='출원';registTypeCode='01'
                        registNumberRaw=$hit.applicationOrRegistration
                        resultTitle=$hit.outcomeTitle
                        projectTitle=$hit.projectTitle
                        performAgency=$hit.performingAgency
                        resultYear=''
                        matchType='official_application_and_project_id_in_same_hit'
                        sourceQueryMode=$plan.mode
                    })
                }
                if($start+10 -gt $r.totalHits -or @($r.rows).Count -lt 10){break}
            }
            $sumHits+=$total;$observed+=$examined
            $firstPageTruncated=($total -gt $examined)
            [void]$checks.Add([pscustomobject]@{
                publicationNumber=$plan.publicationNumber
                applicationNumber=$plan.applicationNumber
                mode=$plan.mode
                query=$plan.query
                status='checked'
                totalHits=$total
                pagesChecked=$nPages
                rowsExamined=$examined
                exactApplicationRows=$exact
                exactApplicationRowsWithProjectOutsidePriorSample=$hasProjectNotSample
                registrationTypeRowsExcluded=$registrations
                unrelatedApplicationRowsExcluded=$unrelated
                truncated=$firstPageTruncated
            })
            Write-Output ('CHECK '+($checks.Count)+'/'+$plans.Count+': '+$plan.mode+
                ' total='+$total+' examined='+$examined+' exactApp='+$exact+
                ' projectOutsidePriorSample='+$hasProjectNotSample+
                ' truncated='+$firstPageTruncated)
        }catch{
            $code=[string]$_.Exception.Message
            if($code -notin @('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404','NTIS_NETWORK_OR_APPROVAL_ERROR',
               'INVALID_OUTCOME_XML','OUTCOME_XML_PARSE_FAILED','UNKNOWN_OUTCOME_RESPONSE',
               'OUTCOME_ROWS_UNRECOGNIZED','INVALID_SEARCH_TERM')){
                $code='NTIS_SEARCH_ERROR'
            }
            $errorCode=$code;$errors++
            [void]$checks.Add([pscustomobject]@{
                publicationNumber=$plan.publicationNumber
                applicationNumber=$plan.applicationNumber
                mode=$plan.mode;query=$plan.query;status='source_error';errorClass=$code
            })
            Write-Output ('CHECK '+($checks.Count)+'/'+$plans.Count+': '+$code)
        }
        if($errorCode -in @('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404','UNKNOWN_OUTCOME_RESPONSE')){break}
    }
    $done=@($checks.ToArray()|Where-Object {$_.status -eq 'checked'}).Count
    $status=if($errors){'partial_errors'}elseif($done -eq $plans.Count){'ready'}else{'incomplete'}
    $timestamp=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $payload=[ordered]@{
        generatedAt=$timestamp
        dossierGeneratedAt=[string]$dossier.generatedAt
        kiprisDeepGeneratedAt=[string]$deep.generatedAt
        ntisProjectsGeneratedAt=[string]$projects.generatedAt
        ntisProjectDossierGeneratedAt=[string]$projects.dossierGeneratedAt
        status=$status
        mappingProfile=$profile
        collectionMethod='approved_pc_rpatent_keyword_discovery'
        targetCount=$MaxTargets
        plannedQueries=$plans.Count
        completedQueries=$done
        failedQueries=$errors
        pagesPerQueryMax=$MaxPages
        totalSearchHitsAcrossQueries=$sumHits
        scannedOutcomeRows=$observed
        exactPatentAndPriorProjectNumberPairs=$matched.Count
        verifiedDirectPatentProjectLinks=0
        commercializationConfirmed=0
        exclusiveConfirmed=0
        records=@($matched.ToArray())
        checks=@($checks.ToArray())
        warning='Keyword/title/applicant queries are discovery only. Exact NTIS RegistType=출원 and same-HIT ProjectID required. Only 1-3 pages queried. Prior 26 project numbers are a partial sampled subset; 0 matched rows is NOT absence of national R&D patent outcomes.'
    }
    $json=$payload|ConvertTo-Json -Depth 15
    if($json.Contains($key) -or $json -match '(?i)apprvKey|authorization|bearer\s'){throw 'POTENTIAL_SECRET_EXPORT_ABORTED'}
    [System.IO.File]::WriteAllText($outFile,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
    Write-Output ('RESULT: '+$status+'; queries='+$done+'/'+$plans.Count+'; examined='+$observed+'; officialNumberPairs='+$matched.Count)
    Write-Output 'OUTPUT_FILE: ntis_patent_discovery_pc_latest.json'
    if($OfflineTest){
        if($done -ne $plans.Count -or $errors -ne 0 -or $plans.Count -lt 3){
            throw 'OFFLINE_END_TO_END_FAILED'
        }
        Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue
        Write-Output 'PASS: real KIPRIS plans, synthetic typed official matches, JSON and dedup gate'
    }
}catch{
    # Do not print exception text: network exception may contain secret URL.
    $reason=[string]$_.Exception.Message
    if($reason -notin @('INVALID_PUBLIC_SNAPSHOTS','PUBLIC_SNAPSHOT_DOWNLOAD_FAILED',
        'NO_KIPRIS_MATCHABLE_PATENTS','POTENTIAL_SECRET_EXPORT_ABORTED')){
        $reason='NTIS_DISCOVERY_FAILED'
    }
    Write-Output ('RESULT: '+$reason)
    $allowed=@('READ_KIPRIS_DOSSIER','READ_KIPRIS_DEEP','READ_NTIS_PROJECTS','PLAN_QUERIES','EXECUTE_QUERIES')
    $safePhase=if($phase -in $allowed){$phase}else{'UNSPECIFIED_PHASE'}
    $exceptionType=$_.Exception.GetType().Name -replace '[^A-Za-z0-9]',''
    $line=[int]$_.InvocationInfo.ScriptLineNumber
    Write-Output ('DIAGNOSTIC: PHASE='+$safePhase+'; TYPE='+$exceptionType+'; LINE='+$line)
    if($OfflineTest){Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue}
    exit 2
}finally{$key=$null;$secret=$null}
