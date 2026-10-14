# NTIS 국가R&D 특허 성과검색: 승인된 Windows PC에서만 실행.
# 2024-01-03 공식 매뉴얼 p15-23 + 2026-10-14 승인 PC XML 실측.
# 인증키는 숨김 입력. 파일에는 현재 KIPRIS 정확한 출원번호 +
# NTIS 동일 HIT의 ProjectID까지 일치한 연구 단서만 저장.
param([switch]$SelfTest,[switch]$OfflineTest,[string]$SnapshotRoot='',[ValidateRange(1,12)][int]$MaxTargets=7)
$ErrorActionPreference='Stop'
$api='https://www.ntis.go.kr/rndopen/openApi/public_result'
$raw='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/'
$local=Join-Path $PSScriptRoot 'ntis_patent_outcomes_pc_latest.json'
$profile='ntis_rpatent_2024_manual_registtype_application_v1'
# Safe, fixed phase names only. Do not reveal raw exception messages:
# PowerShell's Invoke-WebRequest errors can contain secret-bearing URLs.
$phase='START'
if($OfflineTest){
    if(!$SnapshotRoot){throw 'OFFLINE_FIXTURE_ROOT_REQUIRED'}
    $local=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_patent_outcome_offline_regression.json'
}

function Normalize-Patent([string]$value){
    if(!$value){return $null}
    $clean=$value -replace '[\s-]',''
    if($clean -match '^10\d{11}$'){return $clean}
    return $null
}
function Text-Clean($node,[int]$limit){
    if($null -eq $node){return ''}
    $value=[regex]::Replace([string]$node.InnerText,'(?i)</?span\b[^>]*>','')
    $value=[regex]::Replace($value,'\s+',' ').Trim()
    if($value.Length -gt $limit){$value=$value.Substring(0,$limit)}
    return $value
}
function Read-OutcomeXml([string]$xml){
    if(!$xml -or $xml.Length -gt 1600000 -or $xml -match '(?i)<!DOCTYPE|<!ENTITY'){throw 'INVALID_OUTCOME_XML'}
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($xml)}catch{throw 'OUTCOME_XML_PARSE_FAILED'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'UNKNOWN_OUTCOME_RESPONSE'}
    $totalNode=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $resultset=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $totalNode -or $null -eq $resultset -or $totalNode.InnerText -notmatch '^\d{1,10}$'){
        throw 'UNKNOWN_OUTCOME_RESPONSE'
    }
    $total=[long]$totalNode.InnerText
    $rows=New-Object System.Collections.ArrayList
    foreach($hit in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
        $number=Text-Clean ($hit.SelectSingleNode('RegistNumber')) 80
        $regtype=$hit.SelectSingleNode('RegistType')
        $regText=Text-Clean $regtype 30
        $regCode=if($null -ne $regtype){[string]$regtype.GetAttribute('code')}else{''}
        $proj=Text-Clean ($hit.SelectSingleNode('ProjectID')) 40
        $id=Text-Clean ($hit.SelectSingleNode('ResultID')) 100
        $rtitle=Text-Clean ($hit.SelectSingleNode('ResultTitle')) 200
        $ptitle=Text-Clean ($hit.SelectSingleNode('ProjectTitle')) 200
        $agency=Text-Clean ($hit.SelectSingleNode('PerformAgency')) 120
        $year=Text-Clean ($hit.SelectSingleNode('Year')) 10
        [void]$rows.Add([pscustomobject]@{
            registNumber=$number;registType=$regText;registTypeCode=$regCode;
            projectNumber=$proj;resultId=$id;resultTitle=$rtitle;
            projectTitle=$ptitle;performAgency=$agency;resultYear=$year
        })
    }
    if($total -gt 0 -and $rows.Count -eq 0){throw 'OUTCOME_POSITIVE_TOTAL_WITHOUT_ROWS'}
    return [pscustomobject]@{totalHits=$total;rows=@($rows.ToArray())}
}
function Query-Official([string]$term,[string]$key,[string]$field){
    if($OfflineTest){
        # Offline mode must exercise indexing/loop/JSON export without
        # connecting to NTIS or using any real API key.
        return [pscustomobject]@{totalHits=0;rows=@()}
    }
    if($term.Length -lt 4 -or $term.Length -gt 110){throw 'INVALID_QUERY'}
    $args=[ordered]@{
        naviCount='30';searchField=$field;addQuery='DBT=PAT'
        query=$term;displayCount='10';sortby='';collection='rpatent'
        boostquery='';userId='';startPosition='1';apprvKey=$key;cmbnApiYn='Y'
    }
    $params=@(foreach($x in $args.GetEnumerator()){
        ([Uri]::EscapeDataString([string]$x.Key))+'='+([Uri]::EscapeDataString([string]$x.Value))
    })
    $url=$api+'?'+($params -join '&')
    $http=$null;$body=$null
    try{
        $response=Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
        $http=[int]$response.StatusCode;$body=[string]$response.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$http=[int]$_.Exception.Response.StatusCode}catch{$http=$null}
        }
        if($null -eq $http){throw 'OUTCOME_NETWORK_OR_IP_ERROR'}
    }finally{$url=$null}
    if($http -ne 200){throw ('OUTCOME_HTTP_'+$http)}
    return Read-OutcomeXml -xml $body
}
function Get-PublicJson([string]$name){
    try{
        if($OfflineTest){
            $file=Join-Path $SnapshotRoot ($name -replace '/',[System.IO.Path]::DirectorySeparatorChar)
            return ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($file,[System.Text.Encoding]::UTF8))
        }
        $response=Invoke-WebRequest -Uri ($raw+$name) -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
        if($response.StatusCode -ne 200 -or $response.Content.Length -gt 2500000){throw 'bad_snapshot'}
        return ConvertFrom-Json -InputObject ([string]$response.Content)
    }catch{throw 'PUBLIC_SNAPSHOT_DOWNLOAD_FAILED'}
}
if($SelfTest){
    $test='<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT><ResultID>PTO-2026-0001</ResultID><RegistNumber>10-2025-0039383</RegistNumber><RegistType code="01">출원</RegistType><ProjectID>2410019058</ProjectID><ResultTitle>Patent</ResultTitle><ProjectTitle>Project</ProjectTitle><PerformAgency>Agency</PerformAgency></HIT></RESULTSET></RESULT>'
    $parsed=Read-OutcomeXml -xml $test
    if($parsed.rows.Count -ne 1 -or $parsed.rows[0].registTypeCode -ne '01' -or
       $parsed.rows[0].projectNumber -ne '2410019058' -or
       (Normalize-Patent $parsed.rows[0].registNumber) -ne '1020250039383'){throw 'SELFTEST_OUTCOME_MAPPING_FAILED'}
    if((Normalize-Patent '10-2025-0039383') -ne '1020250039383' -or
       (Normalize-Patent '10-2008-0017515') -ne '1020080017515'){throw 'SELFTEST_PATENT_FORMAT_FAILED'}
    try{[void](Read-OutcomeXml -xml '<html>Forbidden</html>');throw 'SELFTEST_FAIL_OPEN'}
    catch{if($_.Exception.Message -ne 'UNKNOWN_OUTCOME_RESPONSE'){throw}}
    Write-Output 'PASS: official RegistNumber, RegistType, ProjectID and ResultID parse; HTML rejected'
    exit 0
}
Write-Output 'NTIS PATENT OUTCOME CHECK - approved Windows PC (diagnostic build)'
Write-Output '2024 official XML fields. Exact KIPRIS application + NTIS project pairs only.'
Write-Output 'Key hidden; errors show only safe PHASE/TYPE/LINE, never URLs or exception text.'
$key=$null;$secret=$null
if($OfflineTest){
    Write-Output 'OFFLINE_TEST: local public JSON snapshots only, no NTIS request or key'
    $key='LOCAL_OFFLINE_TEST_ONLY'
}else{
    $phase='READ_HIDDEN_KEY'
    $secret=Read-Host 'NTIS approved performance-search API key (hidden)' -AsSecureString
    $ptr=[IntPtr]::Zero
    try{
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}
}
try{
    $phase='LOAD_PATENT_DOSSIER'
    $dossier=Get-PublicJson 'digests/patent_rnd_dossiers_latest.json'
    $phase='LOAD_KIPRIS_DEEP'
    $deep=Get-PublicJson 'digests/patent_deep_latest.json'
    $phase='LOAD_NTIS_PROJECTS'
    $projects=Get-PublicJson 'digests/ntis_project_leads_latest.json'
    $phase='VERIFY_INPUT_SNAPSHOTS'
    if($dossier.status -ne 'research_only' -or $projects.status -ne 'ready' -or
       $null -eq $dossier.dossiers -or $null -eq $deep.investigations){throw 'INPUT_SNAPSHOTS_UNVERIFIED'}
    $phase='INDEX_OFFICIAL_PROJECTS'
    $projectIDs=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach($check in @($projects.checks)){
        if($check.status -ne 'checked'){continue}
        foreach($row in @($check.records)){
            $pid=[string]$row.projectNumber
            if($pid -match '^\d{10}$'){[void]$projectIDs.Add($pid)}
        }
    }
    $phase='INDEX_KIPRIS_APPLICATIONS'
    $patentApps=@{}
    foreach($p in @($deep.investigations)){
        $pub=Normalize-Patent ([string]$p.publicationNumber)
        $app=Normalize-Patent ([string]$p.applicationNumber)
        if(!$pub -or !$app){continue}
        if(!$patentApps.ContainsKey($pub)){$patentApps[$pub]=New-Object 'System.Collections.Generic.HashSet[string]'}
        [void]$patentApps[$pub].Add($app)
    }
    $phase='BUILD_PATENT_TARGETS'
    $targets=New-Object System.Collections.ArrayList
    foreach($p in @($dossier.dossiers)){
        $pub=Normalize-Patent ([string]$p.publicationNumber)
        if($pub -and $patentApps.ContainsKey($pub) -and $patentApps[$pub].Count -eq 1){
            $app=@($patentApps[$pub])[0]
            [void]$targets.Add([pscustomobject]@{publicationNumber=$pub;applicationNumber=$app})
            if($targets.Count -ge $MaxTargets){break}
        }
    }
    if($targets.Count -eq 0){throw 'NO_KIPRIS_APPLICATION_NUMBERS'}
    $phase='PREPARE_OUTCOME_QUERIES'
    $checks=New-Object System.Collections.ArrayList
    $matched=New-Object System.Collections.ArrayList
    $keys=New-Object 'System.Collections.Generic.HashSet[string]'
    $errors=0;$observed=0
    $phase='EXECUTE_OUTCOME_QUERIES'
    foreach($t in @($targets.ToArray())){
        $lastError=$null;$res=$null
        try{
            # OG = 출원등록번호 according to manual p15.
            $res=Query-Official -term $t.applicationNumber -key $key -field 'OG'
            # p22 actual example omits searchField: one fallback for zero hits.
            if($res.totalHits -eq 0){$res=Query-Official -term $t.applicationNumber -key $key -field ''}
            $observed+=$res.rows.Count
            $matches=0;$appRows=0
            foreach($hit in @($res.rows)){
                # RegistNumber can be a registered-patent number. Compare ONLY
                # when RegistType explicitly says APPLICATION code 01.
                $n=Normalize-Patent ([string]$hit.registNumber)
                if($hit.registType -ne '출원' -or $hit.registTypeCode -ne '01' -or
                   $n -ne $t.applicationNumber){continue}
                $appRows++
                if(!$projectIDs.Contains([string]$hit.projectNumber)){continue}
                if($hit.resultId -notmatch '^[A-Za-z0-9_-]{5,100}$'){continue}
                $dedupe=$t.publicationNumber+'|'+$hit.projectNumber+'|'+$hit.resultId
                if(!$keys.Add($dedupe)){continue}
                [void]$matched.Add([pscustomobject]@{
                    publicationNumber=$t.publicationNumber
                    patentApplicationNumber=$t.applicationNumber
                    patentPublicationNumber=$null
                    projectNumber=$hit.projectNumber
                    sourceOfficialRecordId=$hit.resultId
                    sourceFieldMappingVerified=$true
                    registType='출원';registTypeCode='01'
                    registNumberRaw=$hit.registNumber
                    resultTitle=$hit.resultTitle
                    projectTitle=$hit.projectTitle
                    performAgency=$hit.performAgency
                    resultYear=$hit.resultYear
                })
                $matches++
            }
            [void]$checks.Add([pscustomobject]@{
                publicationNumber=$t.publicationNumber;applicationNumber=$t.applicationNumber
                status='checked';totalHits=$res.totalHits;rowsObserved=$res.rows.Count
                exactApplicationRows=$appRows;numberProjectMatches=$matches
            })
            Write-Output ('CHECK: official outcome hits '+$res.totalHits+', exact application rows '+$appRows+', project number pairs '+$matches)
        }catch{
            $code=[string]$_.Exception.Message
            if($code -notin @('OUTCOME_HTTP_401','OUTCOME_HTTP_403','OUTCOME_HTTP_404',
                'OUTCOME_NETWORK_OR_IP_ERROR','INVALID_OUTCOME_XML','OUTCOME_XML_PARSE_FAILED',
                'UNKNOWN_OUTCOME_RESPONSE','OUTCOME_POSITIVE_TOTAL_WITHOUT_ROWS')){
                $code='OUTCOME_QUERY_ERROR'
            }
            $lastError=$code;$errors++
            [void]$checks.Add([pscustomobject]@{
                publicationNumber=$t.publicationNumber;applicationNumber=$t.applicationNumber
                status='source_error';errorClass=$code
            })
            Write-Output ('CHECK: '+$code)
        }
        if($lastError -in @('OUTCOME_HTTP_401','OUTCOME_HTTP_403','OUTCOME_HTTP_404','UNKNOWN_OUTCOME_RESPONSE')){break}
    }
    $completed=@($checks.ToArray() | Where-Object {$_.status -eq 'checked'}).Count
    $status=if($errors -gt 0){'partial_official_patent_outcomes'}
            elseif($completed -eq $targets.Count){'verified_official_patent_outcomes'}
            else{'source_error'}
    $now=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $output=[ordered]@{
        generatedAt=$now;dossierGeneratedAt=[string]$dossier.generatedAt
        projectSourceGeneratedAt=[string]$projects.generatedAt
        projectDossierGeneratedAt=[string]$projects.dossierGeneratedAt
        kiprisDeepGeneratedAt=[string]$deep.generatedAt
        status=$status;mappingProfile=$profile
        collectionMethod='approved_pc_rpatent_official_manual'
        targetCount=$targets.Count;completedTargets=$completed;errorTargets=$errors
        matchingOutcomeRows=$matched.Count;sampleOutcomeRowsObserved=$observed
        projectNumbersInKeywordSnapshot=$projectIDs.Count
        records=@($matched.ToArray());checks=@($checks.ToArray())
        confirmedPatentProjectLinks=0;commercializationConfirmed=0;exclusiveConfirmed=0
        warning='Exact official RegistType=출원/RegistNumber and ProjectID pairs are reporter review leads only. Registration numbers, publication numbers and product adoption NOT inferred. The PC project snapshot may be older than the dossier.'
    }
    $phase='WRITE_REVIEW_JSON'
    $json=$output | ConvertTo-Json -Depth 15
    if($json.Contains($key)){throw 'CREDENTIAL_EXPOSURE_ABORTED'}
    [System.IO.File]::WriteAllText($local,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
    Write-Output ('RESULT: '+$status+'; completed '+$completed+'; exact source number pairs '+$matched.Count)
    Write-Output 'OUTPUT: ntis_patent_outcomes_pc_latest.json (review file before sharing)'
    if($OfflineTest){
        if($completed -ne $targets.Count -or $targets.Count -ne 7){
            throw 'OFFLINE_EXPECTED_SEVEN_PATENT_TARGETS'
        }
        Remove-Item -LiteralPath $local -Force -ErrorAction SilentlyContinue
        Write-Output 'PASS: all 7 current KIPRIS application IDs, offline queries and JSON assembly'
    }
}catch{
    $reason=[string]$_.Exception.Message
    if($reason -notin @('INPUT_SNAPSHOTS_UNVERIFIED','PUBLIC_SNAPSHOT_DOWNLOAD_FAILED',
        'NO_KIPRIS_APPLICATION_NUMBERS','CREDENTIAL_EXPOSURE_ABORTED')){
        $reason='OUTCOME_PC_COLLECTION_FAILED'
    }
    Write-Output ('RESULT: '+$reason)
    $safePhases=@('LOAD_PATENT_DOSSIER','LOAD_KIPRIS_DEEP','LOAD_NTIS_PROJECTS',
        'VERIFY_INPUT_SNAPSHOTS','INDEX_OFFICIAL_PROJECTS',
        'INDEX_KIPRIS_APPLICATIONS','BUILD_PATENT_TARGETS',
        'PREPARE_OUTCOME_QUERIES','EXECUTE_OUTCOME_QUERIES','WRITE_REVIEW_JSON')
    $label=if($safePhases -contains $phase){$phase}else{'UNSPECIFIED_PHASE'}
    $exceptionType=$_.Exception.GetType().Name -replace '[^A-Za-z0-9]',''
    $line=[int]$_.InvocationInfo.ScriptLineNumber
    Write-Output ('DIAGNOSTIC: PHASE='+$label+'; TYPE='+$exceptionType+'; LINE='+$line)
    if($OfflineTest){Remove-Item -LiteralPath $local -Force -ErrorAction SilentlyContinue}
    exit 2
}finally{$key=$null;$secret=$null}
