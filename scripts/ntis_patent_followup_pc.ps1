# NTIS targeted patent-outcome follow-up from a fixed historical PC audit.
# This script runs only on the NTIS approved Windows PC (PowerShell 5.1+).
# Credentials, raw URLs, and unrelated patent HIT details are never exported.
param([switch]$SelfTest,[switch]$OfflineTest,[switch]$KeepOfflineOutput,[string]$SnapshotRoot='')
$ErrorActionPreference='Stop'
$api='https://www.ntis.go.kr/rndopen/openApi/public_result'
$repo='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/'
$output=Join-Path $PSScriptRoot 'ntis_patent_followup_pc_latest.json'
$phase='START'
if($OfflineTest){
    if(!$SnapshotRoot){throw 'OFFLINE_ROOT_REQUIRED'}
    $output=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_patent_followup_offline.json'
}
function Patent([string]$s){
    $s=$s -replace '[\s-]',''
    if($s -match '^10\d{11}$'){return $s}
    return $null
}
function Extract($node,[int]$limit){
    if($null -eq $node){return ''}
    $s=[regex]::Replace([string]$node.InnerText,'(?i)</?span\b[^>]*>','')
    $s=[regex]::Replace($s,'\s+',' ').Trim()
    if($s.Length -gt $limit){$s=$s.Substring(0,$limit)}
    return $s
}
function ReadNtis([string]$xml){
    if(!$xml -or $xml.Length -gt 1500000 -or $xml -match '(?i)<!DOCTYPE|<!ENTITY'){
        throw 'BAD_NTIS_XML'
    }
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($xml)}catch{throw 'BAD_NTIS_XML'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'UNKNOWN_NTIS_SCHEMA'}
    $total=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $total -or $null -eq $set -or $total.InnerText -notmatch '^\d{1,10}$'){
        throw 'UNKNOWN_NTIS_SCHEMA'
    }
    $rows=New-Object System.Collections.ArrayList
    foreach($hit in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
        $kind=$hit.SelectSingleNode('RegistType')
        [void]$rows.Add([pscustomobject]@{
            regNumber=(Extract ($hit.SelectSingleNode('RegistNumber')) 80)
            regType=(Extract $kind 30)
            regCode=if($null -ne $kind){[string]$kind.GetAttribute('code')}else{''}
            projectNumber=(Extract ($hit.SelectSingleNode('ProjectID')) 40)
            resultId=(Extract ($hit.SelectSingleNode('ResultID')) 100)
            resultTitle=(Extract ($hit.SelectSingleNode('ResultTitle')) 200)
            projectTitle=(Extract ($hit.SelectSingleNode('ProjectTitle')) 200)
            agency=(Extract ($hit.SelectSingleNode('PerformAgency')) 120)
        })
    }
    $count=[long]$total.InnerText
    if($count -gt 0 -and $rows.Count -eq 0){throw 'NTIS_TOTAL_WITHOUT_ROWS'}
    if($rows.Count -gt 10){throw 'UNEXPECTED_PAGE_SIZE'}
    return [pscustomobject]@{totalHits=$count;rows=@($rows.ToArray())}
}
function PublicData([string]$path){
    try{
        if($OfflineTest){
            $f=Join-Path $SnapshotRoot ($path -replace '/',[System.IO.Path]::DirectorySeparatorChar)
            return ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($f,[System.Text.Encoding]::UTF8))
        }
        $r=Invoke-WebRequest -Uri ($repo+$path) -Method Get -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        if([int]$r.StatusCode -ne 200 -or $r.Content.Length -gt 160000){throw 'BAD_PUBLIC_JSON'}
        return ConvertFrom-Json -InputObject ([string]$r.Content)
    }catch{throw 'PUBLIC_DATA_FETCH_FAILED'}
}
function CallNtis([string]$term,[string]$key,[int]$page,[long]$originalTotal){
    if($OfflineTest){
        $total=if($originalTotal -gt 0){$originalTotal}else{3}
        $count=if($originalTotal -gt 0){10}else{3}
        $xml='<RESULT><TOTALHITS>'+$total+'</TOTALHITS><RESULTSET>'
        for($i=0;$i -lt $count;$i++){
            $code=if($i -eq 1){'02'}else{'01'}
            $kind=if($i -eq 1){'등록'}else{'출원'}
            $num=if($i -gt 1){'10-2020-9999999'}else{'10-2025-0039383'}
            $xml+='<HIT><ResultID>MOCK'+$page+'X'+$i+'</ResultID><RegistNumber>'+
                $num+'</RegistNumber><RegistType code="'+$code+'">'+$kind+
                '</RegistType><ProjectID>2410019058</ProjectID>'+
                '<ResultTitle>Test result</ResultTitle><ProjectTitle>Test project</ProjectTitle></HIT>'
        }
        return ReadNtis ($xml+'</RESULTSET></RESULT>')
    }
    if($term.Length -lt 3 -or $term.Length -gt 70 -or $page -lt 1 -or $page -gt 3){
        throw 'INVALID_QUERY'
    }
    $params=[ordered]@{
        naviCount='30';searchField='';addQuery='DBT=PAT';query=$term
        displayCount='10';sortby='';collection='rpatent';boostquery=''
        userId='';startPosition=[string](1+($page-1)*10)
        apprvKey=$key;cmbnApiYn='Y'
    }
    $encoded=@(foreach($e in $params.GetEnumerator()){
        [Uri]::EscapeDataString([string]$e.Key)+'='+[Uri]::EscapeDataString([string]$e.Value)
    })
    $url=$api+'?'+($encoded -join '&')
    $status=$null;$content=$null
    try{
        $response=Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        $status=[int]$response.StatusCode;$content=[string]$response.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$status=[int]$_.Exception.Response.StatusCode}catch{$status=$null}
        }
        if($null -eq $status){throw 'NTIS_ACCESS_ERROR'}
    }finally{$url=$null}
    if($status -ne 200){throw ('NTIS_HTTP_'+$status)}
    return ReadNtis $content
}
function CheckPlan($plan,$original){
    if($plan.planVersion -ne 'ntis_rpatent_followup_v1' -or
       $original.status -ne 'ready' -or
       $original.mappingProfile -ne 'ntis_rpatent_2024_manual_keyword_discovery_v1' -or
       $plan.sourceDiscoveryGeneratedAt -ne $original.generatedAt -or
       $plan.sourceDossierGeneratedAt -ne $original.dossierGeneratedAt -or
       $plan.sourceKiprisDeepGeneratedAt -ne $original.kiprisDeepGeneratedAt -or
       $plan.sourceNtisProjectsGeneratedAt -ne $original.ntisProjectsGeneratedAt -or
       $plan.sourceNtisProjectDossierGeneratedAt -ne $original.ntisProjectDossierGeneratedAt){
        throw 'FOLLOWUP_SOURCE_MISMATCH'
    }
    if($plan.uniqueQueries -ne @($plan.tasks).Count -or
       $plan.uniqueQueries -ne 11 -or $plan.maximumHttpRequests -ne 15){
        throw 'UNAPPROVED_PLAN_BUDGET'
    }
    $technologies=@{};$applicants=@{}
    foreach($q in @($original.checks)){
        if($q.mode -eq 'technology'){$technologies[[string]$q.publicationNumber]=$q}
        if($q.mode -eq 'applicant'){$applicants[[string]$q.publicationNumber]=$q}
    }
    $seen=New-Object 'System.Collections.Generic.HashSet[string]'
    $calls=0
    foreach($task in @($plan.tasks)){
        $q=[string]$task.query
        $pages=@($task.pages)
        if($q.Length -lt 3 -or $q.Length -gt 70 -or !$pages.Count){throw 'INVALID_PLAN_QUERY'}
        if(!$seen.Add($q+'|'+($pages -join ','))){throw 'DUPLICATED_QUERY'}
        $calls+=$pages.Count
        foreach($target in @($task.targets)){
            $pub=[string]$target.publicationNumber
            $app=[string]$target.applicationNumber
            if(!$technologies.ContainsKey($pub) -or
               $technologies[$pub].applicationNumber -ne $app -or
               $app -notmatch '^10\d{11}$'){throw 'UNKNOWN_OFFICIAL_PATENT'}
            if($task.strategy -eq 'technology_next_pages'){
                if($q -ne $technologies[$pub].query -or
                   !$technologies[$pub].truncated -or
                   $technologies[$pub].totalHits -gt 300 -or
                   $pages.Count -ne 2 -or $pages[0] -ne 2 -or $pages[1] -ne 3 -or
                   $task.sourceTotalHits -ne $technologies[$pub].totalHits){
                    throw 'UNSAFE_HISTORICAL_PAGINATION'
                }
            }elseif($task.strategy -eq 'corporate_technology_narrowing'){
                if(!$applicants.ContainsKey($pub) -or
                   $q -ne ([string]$applicants[$pub].query+' '+[string]$technologies[$pub].query) -or
                   $pages.Count -ne 1 -or $pages[0] -ne 1 -or
                   $null -ne $task.sourceTotalHits){
                    throw 'UNVERIFIED_NARROW_QUERY'
                }
            }else{throw 'UNKNOWN_STRATEGY'}
        }
    }
    if($calls -ne 15){throw 'UNEXPECTED_REQUEST_COUNT'}
}
if($SelfTest){
    $mock='<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT>'+
          '<ResultID>TEST12345</ResultID><RegistNumber>10-2025-0039383</RegistNumber>'+
          '<RegistType code="01">출원</RegistType><ProjectID>2410019058</ProjectID>'+
          '</HIT></RESULTSET></RESULT>'
    $x=ReadNtis $mock
    if($x.rows.Count -ne 1 -or $x.rows[0].regCode -ne '01' -or
       (Patent $x.rows[0].regNumber) -ne '1020250039383'){throw 'SELFTEST_FAILED'}
    try{[void](ReadNtis '<html>login</html>');throw 'HTML_ACCEPTED'}
    catch{if($_.Exception.Message -ne 'UNKNOWN_NTIS_SCHEMA'){throw}}
    Write-Output 'PASS: official patent number XML type and invalid-source rejection'
    exit 0
}
Write-Output 'NTIS official patent R&D follow-up (2026-10-14 snapshot)'
Write-Output '15 bounded calls; only exact KIPRIS application in official outcome HIT is kept.'
$key=$null;$secure=$null
if($OfflineTest){
    Write-Output 'OFFLINE_TEST: 11 planned queries, synthetic NTIS rows, no key or live requests'
    $key='LOCAL_FAKE_KEY'
}else{
    $secure=Read-Host 'Approved NTIS performance-search key (hidden)' -AsSecureString
    $ptr=[IntPtr]::Zero
    try{
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}
}
try{
    $phase='READ_FOLLOWUP_PLAN'
    $plan=PublicData 'digests/ntis_patent_followup_plan_latest.json'
    $phase='READ_OLDER_DISCOVERY'
    $previous=PublicData 'digests/ntis_patent_discovery_pc_latest.json'
    $phase='VERIFY_PINNED_PLAN'
    CheckPlan $plan $previous
    $phase='READ_PRIOR_NTIS_PROJECTS'
    $projects=PublicData 'digests/ntis_project_leads_latest.json'
    if($projects.generatedAt -ne $plan.sourceNtisProjectsGeneratedAt -or
       $projects.dossierGeneratedAt -ne $plan.sourceNtisProjectDossierGeneratedAt){
        throw 'OLD_PROJECT_SOURCE_CHANGED'
    }
    $projectIds=New-Object 'System.Collections.Generic.HashSet[string]'
    foreach($c in @($projects.checks)){
        if($c.status -ne 'checked'){continue}
        foreach($p in @($c.records)){
            $projectNumber=[string]$p.projectNumber
            if($projectNumber -match '^\d{10}$'){[void]$projectIds.Add($projectNumber)}
        }
    }
    $phase='FOLLOWUP_QUERIES'
    $records=New-Object System.Collections.ArrayList
    $checks=New-Object System.Collections.ArrayList
    $seen=New-Object 'System.Collections.Generic.HashSet[string]'
    $requests=0;$examined=0;$errors=0;$outsideOldSubset=0
    foreach($task in @($plan.tasks)){
        $requestPages=@($task.pages)
        $complete=New-Object System.Collections.ArrayList
        $rows=0;$exact=0;$outside=0;$registered=0;$other=0
        $total=$null;$failure=$null
        $idSeen=New-Object 'System.Collections.Generic.HashSet[string]'
        foreach($pageItem in $requestPages){
            $page=[int]$pageItem
            try{
                if($requests -ge 15){throw 'OVER_REQUEST_BUDGET'}
                $requests+=1
                $response=CallNtis ([string]$task.query) $key $page ([long]$task.sourceTotalHits)
                if($null -eq $total){$total=$response.totalHits}
                if($response.totalHits -ne $total){throw 'TOTAL_CHANGED_BETWEEN_PAGES'}
                if($task.strategy -eq 'technology_next_pages' -and
                   $total -ne [long]$task.sourceTotalHits){throw 'HISTORICAL_TOTAL_CHANGED'}
                if($total -ge (1+($page-1)*10) -and @($response.rows).Count -eq 0){
                    throw 'NTIS_EMPTY_PAGE_WITH_RESULTS'
                }
                [void]$complete.Add($page)
                $rows+=@($response.rows).Count
                $examined+=@($response.rows).Count
                foreach($hit in @($response.rows)){
                    if($hit.resultId -match '^[A-Za-z0-9_-]{5,100}$' -and
                       !$idSeen.Add($hit.resultId)){throw 'REPEATED_OUTCOME_IN_PAGES'}
                    if($hit.regType -ne '출원' -or $hit.regCode -ne '01'){
                        $registered++;continue
                    }
                    $app=Patent ([string]$hit.regNumber)
                    $targets=@($task.targets | Where-Object {$_.applicationNumber -eq $app})
                    if(!$targets.Count){$other++;continue}
                    $exact+=1
                    $proj=[string]$hit.projectNumber
                    if($proj -notmatch '^\d{10}$'){continue}
                    $sample=$projectIds.Contains($proj)
                    if(!$sample){$outside++;$outsideOldSubset++}
                    if($hit.resultId -notmatch '^[A-Za-z0-9_-]{5,100}$'){continue}
                    foreach($target in $targets){
                        $marker=$target.publicationNumber+'|'+$hit.resultId+'|'+$proj
                        if(!$seen.Add($marker)){continue}
                        [void]$records.Add([pscustomobject]@{
                            publicationNumber=[string]$target.publicationNumber
                            patentApplicationNumber=[string]$target.applicationNumber
                            projectNumber=$proj
                            projectInOlder26ProjectSubset=[bool]$sample
                            officialOutcomeId=$hit.resultId
                            registType='출원'
                            registTypeCode='01'
                            registNumberRaw=$hit.regNumber
                            outcomeTitle=$hit.resultTitle
                            projectTitle=$hit.projectTitle
                            performingAgency=$hit.agency
                            query=[string]$task.query
                            strategy=[string]$task.strategy
                            page=$page
                            officialFieldsInSameHit=$true
                            patentProjectLinkConfirmed=$false
                            commercializationConfirmed=$false
                            exclusiveConfirmed=$false
                        })
                    }
                }
                if(@($response.rows).Count -lt 10 -and $total -gt ($page*10)){
                    throw 'UNEXPECTED_SHORT_PAGE'
                }
            }catch{
                $reason=[string]$_.Exception.Message
                $known=@('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404','NTIS_ACCESS_ERROR',
                         'BAD_NTIS_XML','UNKNOWN_NTIS_SCHEMA','NTIS_TOTAL_WITHOUT_ROWS',
                         'UNEXPECTED_PAGE_SIZE','OVER_REQUEST_BUDGET',
                         'TOTAL_CHANGED_BETWEEN_PAGES','HISTORICAL_TOTAL_CHANGED',
                         'NTIS_EMPTY_PAGE_WITH_RESULTS','REPEATED_OUTCOME_IN_PAGES',
                         'UNEXPECTED_SHORT_PAGE')
                $failure=if($reason -in $known){$reason}else{'QUERY_FAILED'}
                break
            }
        }
        if($failure){$errors++}
        [void]$checks.Add([pscustomobject]@{
            query=[string]$task.query
            strategy=[string]$task.strategy
            sourceTotalHits=$task.sourceTotalHits
            pagesRequested=@($requestPages)
            pagesCompleted=@($complete.ToArray())
            targets=@($task.targets)
            status=if($failure){'source_error'}else{'checked'}
            errorClass=if($failure){$failure}else{$null}
            newQueryTotalHits=if($task.strategy -eq 'corporate_technology_narrowing'){$total}else{$null}
            newlyScannedRows=$rows
            exactApplicationRows=$exact
            exactApplicationWithProjectOutsideOlderSubset=$outside
            registrationTypeExcluded=$registered
            unrelatedApplicationExcluded=$other
            truncated=if($null -ne $total){$total -gt ((@($complete.ToArray()) | Measure-Object -Maximum).Maximum * 10)}else{$true}
        })
        $displayStatus=if($failure){$failure}else{'checked'}
        Write-Output ('CHECK '+$checks.Count+'/'+$plan.uniqueQueries+
            ' strategy='+$task.strategy+' pages='+(@($complete.ToArray()) -join ',')+
            ' rows='+$rows+' exactApp='+$exact+' projectOutsideOldSubset='+$outside+
            ' status='+$displayStatus)
        if($failure -in @('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404','UNKNOWN_NTIS_SCHEMA')){break}
    }
    $completed=@($checks.ToArray()|Where-Object {$_.status -eq 'checked'}).Count
    $status=if($errors){'partial_errors'}elseif($completed -eq $plan.uniqueQueries){'ready'}else{'incomplete'}
    $now=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $result=[ordered]@{
        generatedAt=$now
        planGeneratedAt=[string]$plan.generatedAt
        sourceDiscoveryGeneratedAt=[string]$plan.sourceDiscoveryGeneratedAt
        sourceDossierGeneratedAt=[string]$plan.sourceDossierGeneratedAt
        status=$status
        collectionMethod='approved_pc_ntis_rpatent_targeted_followup'
        planVersion='ntis_rpatent_followup_v1'
        plannedQueries=$plan.uniqueQueries
        completedQueries=$completed
        failedQueries=$errors
        maxHttpRequests=$plan.maximumHttpRequests
        actualHttpRequests=$requests
        additionalScannedRows=$examined
        applicationMatchRowsOutsideOldProjectSubset=$outsideOldSubset
        exactApplicationProjectNumberReviewCandidates=$records.Count
        officialPatentProjectLinksConfirmed=0
        commercializationConfirmed=0
        exclusiveConfirmed=0
        checks=@($checks.ToArray())
        records=@($records.ToArray())
        warning='Historical 2026-10-14 source. Corporate+technology query semantics may not be AND. Every candidate requires exact RegistType=출원 and application number with ProjectID in one official HIT. Previous 26 project IDs are a partial subset. No news/exclusive or product application claim.'
    }
    $json=$result | ConvertTo-Json -Depth 16
    if($json.Contains($key) -or $json -match '(?i)apprvKey|authorization|bearer\s'){
        throw 'POTENTIAL_KEY_EXPOSURE'
    }
    [System.IO.File]::WriteAllText($output,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
    Write-Output ('RESULT: '+$status+'; queries='+$completed+'/'+$plan.uniqueQueries+
        ' requests='+$requests+'/'+$plan.maximumHttpRequests+
        ' additionalRows='+$examined+' exactReviewPairs='+$records.Count)
    Write-Output 'OUTPUT_FILE: ntis_patent_followup_pc_latest.json'
    if($OfflineTest){
        if($completed -ne $plan.uniqueQueries -or $requests -ne 15 -or
           $records.Count -lt 1){throw 'OFFLINE_END_TO_END_FAILED'}
        if(!$KeepOfflineOutput){Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue}
        Write-Output 'PASS: 11 plans / 15 simulated queries / strict number-type gate / JSON export'
    }
}catch{
    # Never echo exception text: it can include approved secret-bearing URLs.
    $type=$_.Exception.GetType().Name -replace '[^A-Za-z0-9]',''
    $line=[int]$_.InvocationInfo.ScriptLineNumber
    Write-Output 'RESULT: FOLLOWUP_COLLECTION_FAILED'
    Write-Output ('DIAGNOSTIC: PHASE='+$phase+' TYPE='+$type+' LINE='+$line)
    if($OfflineTest){Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue}
    exit 2
}finally{$key=$null;$secure=$null}
