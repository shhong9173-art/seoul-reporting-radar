# NTIS project-ID -> rpatent outcomes reverse lookup (approved PC only).
# Official 2024 manual: TI searches patent title and project ID; TI03 is the
# detailed project-ID field. Actual REST index semantics remain unverified.
# Never save NTIS key/raw request URLs/unrelated outcome records.
param(
    [switch]$SelfTest,
    [switch]$OfflineTest,
    [switch]$KeepOfflineOutput,
    [string]$SnapshotRoot='',
    [ValidateRange(1,26)][int]$MaxProjects=26
)
$ErrorActionPreference='Stop'
$repo='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/'
$official='https://www.ntis.go.kr/rndopen/openApi/public_result'
$profile='ntis_rpatent_reverse_projectid_v1'
$exportPath=Join-Path $PSScriptRoot 'ntis_project_reverse_pc_latest.json'
$phase='INITIAL'
if($OfflineTest){
    if(!$SnapshotRoot){throw 'OFFLINE_FIXTURE_ROOT_REQUIRED'}
    $exportPath=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_project_reverse_offline.json'
}
function NormalPatent([string]$value){
    if(!$value){return $null}
    $n=$value -replace '[\s-]',''
    if($n -match '^10\d{11}$'){return $n}
    return $null
}
function SafeText($node,[int]$limit){
    if($null -eq $node){return ''}
    $t=[regex]::Replace([string]$node.InnerText,'(?i)</?span\b[^>]*>','')
    $t=[regex]::Replace($t,'\s+',' ').Trim()
    if($t.Length -gt $limit){$t=$t.Substring(0,$limit)}
    return $t
}
function Parse-NtisXml([string]$raw){
    if(!$raw -or $raw.Length -gt 1500000 -or $raw -match '(?i)<!DOCTYPE|<!ENTITY'){
        throw 'NTIS_INVALID_XML'
    }
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($raw)}catch{throw 'NTIS_XML_PARSE_FAILED'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'NTIS_UNRECOGNIZED_XML'}
    $total=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $total -or $null -eq $set -or $total.InnerText -notmatch '^\d{1,10}$'){
        throw 'NTIS_UNRECOGNIZED_XML'
    }
    $rows=New-Object System.Collections.ArrayList
    foreach($node in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
        $rType=$node.SelectSingleNode('RegistType')
        [void]$rows.Add([pscustomobject]@{
            projectNumber=(SafeText ($node.SelectSingleNode('ProjectID')) 30)
            applicationOrRegistration=(SafeText ($node.SelectSingleNode('RegistNumber')) 80)
            registeredKind=(SafeText $rType 30)
            registeredCode=if($null -ne $rType){[string]$rType.GetAttribute('code')}else{''}
            resultId=(SafeText ($node.SelectSingleNode('ResultID')) 100)
            resultTitle=(SafeText ($node.SelectSingleNode('ResultTitle')) 200)
            projectTitle=(SafeText ($node.SelectSingleNode('ProjectTitle')) 200)
            performingAgency=(SafeText ($node.SelectSingleNode('PerformAgency')) 120)
        })
    }
    $hits=[long]$total.InnerText
    if($hits -gt 0 -and $rows.Count -eq 0){throw 'NTIS_POSITIVE_TOTAL_WITHOUT_ROWS'}
    if($rows.Count -gt 10){throw 'NTIS_PAGE_SIZE_EXCEEDED'}
    return [pscustomobject]@{totalHits=$hits;rows=@($rows.ToArray())}
}
function Load-Snapshot([string]$path){
    try{
        if($OfflineTest){
            $source=Join-Path $SnapshotRoot ($path -replace '/',[System.IO.Path]::DirectorySeparatorChar)
            return ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($source,[System.Text.Encoding]::UTF8))
        }
        $r=Invoke-WebRequest -Method Get -Uri ($repo+$path) -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        if([int]$r.StatusCode -ne 200 -or $r.Content.Length -gt 700000){throw 'SOURCE_TOO_LARGE'}
        return ConvertFrom-Json -InputObject ([string]$r.Content)
    }catch{throw 'PUBLIC_SNAPSHOT_FETCH_FAILED'}
}
function Get-Official([string]$project,[string]$key,[string]$mode){
    if($OfflineTest){
        # Synthetic test: one matching 2026 LS / Hanbit outcome.
        # All other projects are independent queries. No live data/keys.
        if($project -eq '2410017896' -and $mode -eq 'primary'){
            return Parse-NtisXml '<RESULT><TOTALHITS>0</TOTALHITS><RESULTSET/></RESULT>'
        }
        if($project -eq '2410017896' -and $mode -eq 'ti03'){
            $body='<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET>'+
                  '<HIT><ProjectID>1111111111</ProjectID><ResultID>UNRELATED001</ResultID>'+
                  '<RegistNumber>10-2025-0039383</RegistNumber>'+
                  '<RegistType code="01">출원</RegistType></HIT></RESULTSET></RESULT>'
            return Parse-NtisXml $body
        }
        $code=if($project -eq '2410019058'){'2410019058'}else{'1111111111'}
        $body='<RESULT><TOTALHITS>3</TOTALHITS><RESULTSET>'+
          '<HIT><ProjectID>'+$code+'</ProjectID><ResultID>MOCK'+$project+'A</ResultID>'+
          '<RegistNumber>10-2025-0039383</RegistNumber><RegistType code="01">출원</RegistType>'+
          '<ResultTitle>Fixture sensor</ResultTitle><ProjectTitle>Fixture project</ProjectTitle></HIT>'+
          '<HIT><ProjectID>'+$project+'</ProjectID><ResultID>MOCK'+$project+'B</ResultID>'+
          '<RegistNumber>10-2025-0039383</RegistNumber><RegistType code="02">등록</RegistType></HIT>'+
          '<HIT><ProjectID>'+$project+'</ProjectID><ResultID>MOCK'+$project+'C</ResultID>'+
          '<RegistNumber>10-2020-9999999</RegistNumber><RegistType code="01">출원</RegistType></HIT>'+
          '</RESULTSET></RESULT>'
        return Parse-NtisXml $body
    }
    if($project -notmatch '^\d{10}$' -or $mode -notin @('primary','ti03')){
        throw 'INVALID_OFFICIAL_PROJECT_LOOKUP'
    }
    $detailed=if($mode -eq 'ti03'){'TI03='+$project+'&DBT=PAT'}else{'DBT=PAT'}
    $args=[ordered]@{
        naviCount='30';searchField='TI';addQuery=$detailed
        query=$project;displayCount='10';sortby='';collection='rpatent'
        boostquery='';userId='';startPosition='1';apprvKey=$key;cmbnApiYn='Y'
    }
    $tokens=@(foreach($p in $args.GetEnumerator()){
        [Uri]::EscapeDataString([string]$p.Key)+'='+[Uri]::EscapeDataString([string]$p.Value)
    })
    $url=$official+'?'+($tokens -join '&')
    $responseCode=$null;$body=$null
    try{
        $r=Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        $responseCode=[int]$r.StatusCode;$body=[string]$r.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$responseCode=[int]$_.Exception.Response.StatusCode}catch{$responseCode=$null}
        }
        if($null -eq $responseCode){throw 'NTIS_NETWORK_OR_APPROVAL_ERROR'}
    }finally{$url=$null}
    if($responseCode -ne 200){throw ('NTIS_HTTP_'+$responseCode)}
    return Parse-NtisXml $body
}
function Validate-Plan($plan,$source,$dossier,$deep){
    if($plan.planVersion -ne $profile -or $plan.projectCount -ne 26 -or
       $plan.maxPrimaryQueries -ne 26 -or $plan.maxFallbackQueries -ne 26 -or
       $plan.absoluteMaxHttpRequests -ne 52 -or
       $plan.projectSourceGeneratedAt -ne $source.generatedAt -or
       $plan.projectSourceDossierGeneratedAt -ne $source.dossierGeneratedAt -or
       $plan.kiprisDossierGeneratedAt -ne $dossier.generatedAt -or
       $plan.kiprisDeepGeneratedAt -ne $deep.generatedAt){
        throw 'SOURCE_OR_REVERSE_PLAN_MISMATCH'
    }
    $projectIds=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach($check in @($source.checks)){
        if($check.status -ne 'checked'){continue}
        foreach($p in @($check.records)){
            $id=[string]$p.projectNumber
            if($id -match '^\d{10}$'){[void]$projectIds.Add($id)}
        }
    }
    if($projectIds.Count -ne 26 -or @($plan.projects).Count -ne 26){
        throw 'PROJECT_POPULATION_CHANGED'
    }
    foreach($p in @($plan.projects)){
        if(!$projectIds.Contains([string]$p.projectNumber)){throw 'UNKNOWN_OFFICIAL_PROJECT'}
    }
    $deepIds=@{}
    foreach($item in @($deep.investigations)){
        $pub=[string]$item.publicationNumber
        $app=NormalPatent ([string]$item.applicationNumber)
        if(!$pub -or !$app){continue}
        if(!$deepIds.ContainsKey($pub)){$deepIds[$pub]=New-Object 'System.Collections.Generic.HashSet[string]'}
        [void]$deepIds[$pub].Add($app)
    }
    $dossierPubs=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach($item in @($dossier.dossiers)){[void]$dossierPubs.Add([string]$item.publicationNumber)}
    foreach($x in @($plan.targetKiprisApplications)){
        $pub=[string]$x.publicationNumber
        $app=[string]$x.applicationNumber
        if(!$dossierPubs.Contains($pub) -or !$deepIds.ContainsKey($pub) -or
           $deepIds[$pub].Count -ne 1 -or !$deepIds[$pub].Contains($app)){
            throw 'UNVERIFIED_KIPRIS_APPLICATION'
        }
    }
}
if($SelfTest){
    $good='<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT>'+
      '<ProjectID>2410019058</ProjectID><ResultID>TEST12345</ResultID>'+
      '<RegistNumber>10-2025-0039383</RegistNumber>'+
      '<RegistType code="01">출원</RegistType></HIT></RESULTSET></RESULT>'
    $x=Parse-NtisXml $good
    if($x.totalHits -ne 1 -or $x.rows.Count -ne 1 -or
       $x.rows[0].projectNumber -ne '2410019058' -or
       $x.rows[0].registeredCode -ne '01' -or
       (NormalPatent $x.rows[0].applicationOrRegistration) -ne '1020250039383'){
        throw 'REVERSE_XML_SELFTEST_FAILED'
    }
    try{[void](Parse-NtisXml '<html>Access denied</html>');throw 'HTML_ACCEPTED'}
    catch{if($_.Exception.Message -ne 'NTIS_UNRECOGNIZED_XML'){throw}}
    Write-Output 'PASS: official ProjectID, RegistNumber/type and unrecognized XML rejection'
    exit 0
}
Write-Output 'NTIS R&D project-ID -> official patent outcomes REVERSE SEARCH'
Write-Output '26 unique public_project IDs. Maximum 52 official calls, one page per mode.'
Write-Output 'Indexing behavior needs registered-PC confirmation. No patent/commercialization claims.'
$key=$null;$secret=$null
if($OfflineTest){$key='OFFLINE_TEST_ONLY'}
else{
    $secret=Read-Host 'Approved NTIS patent performance-search key (hidden)' -AsSecureString
    $ptr=[IntPtr]::Zero
    try{
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
        $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}
}
try{
    $phase='LOAD_REVERSE_PLAN'
    $plan=Load-Snapshot 'digests/ntis_project_reverse_plan_latest.json'
    $phase='LOAD_PROJECT_SOURCE'
    $projects=Load-Snapshot 'digests/ntis_project_leads_latest.json'
    $phase='LOAD_KIPRIS_DOSSIER'
    $dossier=Load-Snapshot 'digests/patent_rnd_dossiers_latest.json'
    $phase='LOAD_KIPRIS_DEEP'
    $deep=Load-Snapshot 'digests/patent_deep_latest.json'
    $phase='VERIFY_PINNED_SOURCES'
    Validate-Plan $plan $projects $dossier $deep
    $apps=@{}
    foreach($t in @($plan.targetKiprisApplications)){
        $app=[string]$t.applicationNumber
        if(!$apps.ContainsKey($app)){$apps[$app]=New-Object System.Collections.ArrayList}
        [void]$apps[$app].Add([string]$t.publicationNumber)
    }
    $records=New-Object System.Collections.ArrayList
    $checks=New-Object System.Collections.ArrayList
    $matchedIds=New-Object 'System.Collections.Generic.HashSet[string]'
    $phase='RUN_OFFICIAL_PROJECTID_SEARCH'
    $calls=0;$errors=0;$totalRows=0;$primaryChecked=0;$fallbackChecked=0
    foreach($project in @($plan.projects | Select-Object -First $MaxProjects)){
        $id=[string]$project.projectNumber
        $modes=New-Object System.Collections.ArrayList
        $inspected=0;$exactProject=0;$applicationType=0;$matchedApps=0
        $otherProjects=0;$registrationExcluded=0;$truncated=$false
        $errorCode=$null;$primaryHits=$null;$fallbackHits=$null
        foreach($mode in @('primary','ti03')){
            if($mode -eq 'ti03' -and $null -ne $primaryHits -and $primaryHits -gt 0){break}
            try{
                if($calls -ge 52){throw 'REVERSE_QUERY_BUDGET_EXCEEDED'}
                $calls++
                $response=Get-Official $id $key $mode
                if($mode -eq 'primary'){$primaryHits=[long]$response.totalHits;$primaryChecked++}
                else{$fallbackHits=[long]$response.totalHits;$fallbackChecked++}
                $truncated=$truncated -or ($response.totalHits -gt @($response.rows).Count)
                $inspected+=@($response.rows).Count
                $totalRows+=@($response.rows).Count
                [void]$modes.Add($mode)
                foreach($hit in @($response.rows)){
                    if($hit.projectNumber -ne $id){$otherProjects++;continue}
                    $exactProject++
                    if($hit.registeredKind -ne '출원' -or $hit.registeredCode -ne '01'){
                        $registrationExcluded++
                        continue
                    }
                    $applicationType++
                    $app=NormalPatent $hit.applicationOrRegistration
                    if(!$app -or !$apps.ContainsKey($app)){continue}
                    if($hit.resultId -notmatch '^[A-Za-z0-9_-]{5,100}$'){continue}
                    $matchedApps++
                    foreach($pub in @($apps[$app].ToArray())){
                        $token=$id+'|'+$pub+'|'+$hit.resultId
                        if(!$matchedIds.Add($token)){continue}
                        [void]$records.Add([pscustomobject]@{
                            projectNumber=$id
                            publicationNumber=$pub
                            applicationNumber=$app
                            officialResultID=$hit.resultId
                            sourceRegistNumber=$hit.applicationOrRegistration
                            sourceRegistType='출원'
                            sourceRegistTypeCode='01'
                            sourceProjectID=$hit.projectNumber
                            resultTitle=$hit.resultTitle
                            projectTitle=$hit.projectTitle
                            performingAgency=$hit.performingAgency
                            searchMode=$mode
                            sameOfficialHitIdentifiers=$true
                            officialPatentProjectOutcomeVerified=$false
                            commercializationConfirmed=$false
                            exclusiveConfirmed=$false
                        })
                    }
                }
                # We only fallback if the documented TI (title / project ID)
                # search returns zero. Even both zero doesn't prove absence.
            }catch{
                $reason=[string]$_.Exception.Message
                $allowed=@('NTIS_INVALID_XML','NTIS_XML_PARSE_FAILED','NTIS_UNRECOGNIZED_XML',
                           'NTIS_POSITIVE_TOTAL_WITHOUT_ROWS','NTIS_PAGE_SIZE_EXCEEDED',
                           'NTIS_NETWORK_OR_APPROVAL_ERROR','NTIS_HTTP_401','NTIS_HTTP_403',
                           'NTIS_HTTP_404','REVERSE_QUERY_BUDGET_EXCEEDED')
                $errorCode=if($reason -in $allowed){$reason}else{'REVERSE_SOURCE_QUERY_ERROR'}
                break
            }
        }
        if($errorCode){$errors++}
        [void]$checks.Add([pscustomobject]@{
            projectNumber=$id
            projectYear=$project.projectYear
            projectTitle=$project.projectTitle
            performingAgency=$project.performingAgency
            earlierKeywordPatentPublications=@($project.earlierKeywordMatchedPatentPublications)
            status=if($errorCode){'source_error'}else{'checked'}
            errorClass=if($errorCode){$errorCode}else{$null}
            searchModesCompleted=@($modes.ToArray())
            primaryTotalHits=$primaryHits
            fallbackTotalHits=$fallbackHits
            rowsInspected=$inspected
            exactProjectIdRows=$exactProject
            differentProjectIdRowsExcluded=$otherProjects
            registrationTypeRowsExcluded=$registrationExcluded
            applicationTypeRows=$applicationType
            matchingKiprisApplicationRows=$matchedApps
            uninspectedPagesRemain=[bool]$truncated
        })
        $statusLabel=if($errorCode){$errorCode}else{'checked'}
        Write-Output ('CHECK '+$checks.Count+'/'+$MaxProjects+
            ' official project '+$id+' modes='+(@($modes.ToArray()) -join ',')+
            ' rows='+$inspected+' exactProject='+$exactProject+
            ' kiprisApplicationMatches='+$matchedApps+' status='+$statusLabel)
        if($errorCode -in @('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404','NTIS_UNRECOGNIZED_XML')){break}
    }
    $complete=@($checks.ToArray()|Where-Object {$_.status -eq 'checked'}).Count
    $status=if($errors){'partial_errors'}elseif($complete -eq $MaxProjects){'ready'}else{'incomplete'}
    $now=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $result=[ordered]@{
        generatedAt=$now
        planVersion=$profile
        planGeneratedAt=[string]$plan.generatedAt
        projectSourceGeneratedAt=[string]$plan.projectSourceGeneratedAt
        projectSourceDossierGeneratedAt=[string]$plan.projectSourceDossierGeneratedAt
        kiprisDossierGeneratedAt=[string]$plan.kiprisDossierGeneratedAt
        kiprisDeepGeneratedAt=[string]$plan.kiprisDeepGeneratedAt
        status=$status
        collectionMethod='approved_pc_ntis_rpatent_reverse_projectid'
        plannedUniqueProjects=$MaxProjects
        completedProjects=$complete
        failedProjects=$errors
        actualHttpRequests=$calls
        maximumHttpRequests=52
        primaryQueriesCompleted=$primaryChecked
        fallbackQueriesCompleted=$fallbackChecked
        rowsInspected=$totalRows
        matchedOfficialProjectApplicationRows=$records.Count
        reviewedNumberPairs=$records.Count
        verifiedPatentProjectOutcomes=0
        confirmedCommercialization=0
        confirmedExclusives=0
        checks=@($checks.ToArray())
        records=@($records.ToArray())
        warning='Per official 2024 NTIS manual TI searches title/project ID; TI03 detailed filter. Live indexing semantics must be observed. An exact ProjectID and KIPRIS application in the SAME NTIS rpatent HIT is an editorial review lead only. Search zero or first-page omission never proves absence. Historical project source, not a current commercialization/exclusive.'
    }
    $json=$result|ConvertTo-Json -Depth 18
    if($json.Contains($key) -or $json -match '(?i)apprvKey|authorization|bearer\s'){
        throw 'UNSAFE_OUTPUT_CREDENTIALS'
    }
    [System.IO.File]::WriteAllText($exportPath,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
    Write-Output ('RESULT: '+$status+'; projects '+$complete+'/'+$MaxProjects+
      '; official calls '+$calls+'/52; scanned '+$totalRows+
      '; KIPRIS number-pair leads '+$records.Count)
    Write-Output 'OUTPUT_FILE: ntis_project_reverse_pc_latest.json'
    if($OfflineTest){
        if($complete -ne $MaxProjects -or $errors -ne 0 -or
           $fallbackChecked -lt 1 -or $records.Count -lt 1){
            throw 'OFFLINE_FULL_PATH_FAILED'
        }
        if(!$KeepOfflineOutput){Remove-Item -LiteralPath $exportPath -Force -ErrorAction SilentlyContinue}
        Write-Output 'PASS: 26 project searches, documented TI03 fallback, strict type+project match and JSON export'
    }
}catch{
    # No exception message or URL: Invoke-WebRequest can contain a secret key.
    $safe=@('LOAD_REVERSE_PLAN','LOAD_PROJECT_SOURCE','LOAD_KIPRIS_DOSSIER',
        'LOAD_KIPRIS_DEEP','VERIFY_PINNED_SOURCES','RUN_OFFICIAL_PROJECTID_SEARCH')
    $label=if($safe -contains $phase){$phase}else{'UNKNOWN_PHASE'}
    $type=$_.Exception.GetType().Name -replace '[^A-Za-z0-9]',''
    $line=[int]$_.InvocationInfo.ScriptLineNumber
    Write-Output 'RESULT: NTIS_REVERSE_PROJECT_COLLECTION_FAILED'
    Write-Output ('DIAGNOSTIC: PHASE='+$label+' TYPE='+$type+' LINE='+$line)
    if($OfflineTest){Remove-Item -LiteralPath $exportPath -Force -ErrorAction SilentlyContinue}
    exit 2
}finally{$key=$null;$secret=$null}
