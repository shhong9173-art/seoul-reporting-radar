# NTIS rpatent positive control: does TI/TI03 index actual ProjectID?
# Windows PowerShell 5.1, user-approved PC/IP only.
# Only aggregate counts and booleans leave the approved PC. Do NOT export
# project IDs or person/agency/title from unrelated outcome records.
param([switch]$SelfTest,[switch]$OfflineTest,[switch]$KeepOfflineOutput)
$ErrorActionPreference='Stop'
$base='https://www.ntis.go.kr/rndopen/openApi/public_result'
$seedTerm='부분방전'
$outFile=Join-Path $PSScriptRoot 'ntis_project_field_probe_pc_latest.json'
$phase='START'
if($OfflineTest){
    $outFile=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_project_field_probe_offline.json'
}
function Read-Official([string]$xml){
    if(!$xml -or $xml.Length -gt 1600000 -or $xml -match '(?i)<!DOCTYPE|<!ENTITY'){
        throw 'UNSAFE_SOURCE_XML'
    }
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($xml)}catch{throw 'BAD_OFFICIAL_XML'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'UNRECOGNIZED_OFFICIAL_RESPONSE'}
    $total=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $total -or $null -eq $set -or $total.InnerText -notmatch '^\d{1,10}$'){
        throw 'UNRECOGNIZED_OFFICIAL_RESPONSE'
    }
    $rows=New-Object System.Collections.ArrayList
    foreach($n in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
        $pNode=$n.SelectSingleNode('ProjectID')
        $rNode=$n.SelectSingleNode('ResultID')
        $id=if($null -ne $pNode){[string]$pNode.InnerText}else{''}
        $resultId=if($null -ne $rNode){[string]$rNode.InnerText}else{''}
        [void]$rows.Add([pscustomobject]@{projectId=$id.Trim();resultId=$resultId.Trim()})
    }
    if([long]$total.InnerText -gt 0 -and $rows.Count -eq 0){throw 'INDEX_HITS_WITHOUT_RECORDS'}
    if($rows.Count -gt 10){throw 'UNEXPECTED_PAGE_SIZE'}
    return [pscustomobject]@{totalHits=[long]$total.InnerText;rows=@($rows.ToArray())}
}
function Query-Official([string]$field,[string]$query,[string]$filter,[string]$key,[string]$mode){
    if($OfflineTest){
        $seed='<RESULT><TOTALHITS>197</TOTALHITS><RESULTSET>'+
        '<HIT><ProjectID>1415076898</ProjectID><ResultID>CONTROL12345</ResultID></HIT>'+
        '<HIT><ProjectID>1415076888</ProjectID><ResultID>UNRELATED12345</ResultID></HIT>'+
        '</RESULTSET></RESULT>'
        if($mode -eq 'seed'){return Read-Official $seed}
        if($mode -in @('project_bi','project_unscoped','ti03_seed')){
            return Read-Official '<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT><ProjectID>1415076898</ProjectID><ResultID>CONTROL12345</ResultID></HIT></RESULTSET></RESULT>'
        }
        return Read-Official '<RESULT><TOTALHITS>0</TOTALHITS><RESULTSET/></RESULT>'
    }
    if($query.Length -lt 3 -or $query.Length -gt 70 -or
       $field -notin @('','TI','BI') -or $filter.Length -gt 70){
        throw 'UNEXPECTED_QUERY_PARAMETERS'
    }
    $args=[ordered]@{
        naviCount='30';searchField=$field;addQuery=$filter;query=$query
        displayCount='10';sortby='';collection='rpatent';boostquery=''
        userId='';startPosition='1';apprvKey=$key;cmbnApiYn='Y'
    }
    $tokens=@(foreach($pair in $args.GetEnumerator()){
        [Uri]::EscapeDataString([string]$pair.Key)+'='+[Uri]::EscapeDataString([string]$pair.Value)
    })
    $url=$base+'?'+($tokens -join '&')
    $code=$null;$content=$null
    try{
        $r=Invoke-WebRequest -Method Get -Uri $url -UseBasicParsing -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
        $code=[int]$r.StatusCode;$content=[string]$r.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$code=[int]$_.Exception.Response.StatusCode}catch{$code=$null}
        }
        if($null -eq $code){throw 'NTIS_NETWORK_OR_APPROVAL_ERROR'}
    }finally{$url=$null}
    if($code -ne 200){throw ('NTIS_HTTP_'+$code)}
    return Read-Official $content
}
function Summary($response,[string]$project,[string]$recordId,[string]$name){
    $matchingProject=@($response.rows | Where-Object {$_.projectId -eq $project}).Count
    $matchingExact=@($response.rows | Where-Object {
        $_.projectId -eq $project -and $_.resultId -eq $recordId
    }).Count
    return [pscustomobject]@{
        mode=$name
        status='checked'
        totalHits=[long]$response.totalHits
        rowsInspected=@($response.rows).Count
        exactReferenceProjectRows=$matchingProject
        exactReferenceOutcomeRows=$matchingExact
        additionalPagesNotChecked=($response.totalHits -gt @($response.rows).Count)
        errorClass=$null
    }
}
function ErrorSummary([string]$name,[string]$code){
    return [pscustomobject]@{
        mode=$name;status='source_error';totalHits=$null;rowsInspected=0
        exactReferenceProjectRows=0;exactReferenceOutcomeRows=0
        additionalPagesNotChecked=$true;errorClass=$code
    }
}
if($SelfTest){
    $x=Read-Official '<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT><ProjectID>1415076898</ProjectID><ResultID>CTRL12345</ResultID></HIT></RESULTSET></RESULT>'
    if($x.rows.Count -ne 1 -or $x.rows[0].projectId -ne '1415076898'){throw 'XML_FIELD_TEST_FAILED'}
    try{[void](Read-Official '<html>forbidden</html>');throw 'BAD_HTML_ACCEPTED'}
    catch{if($_.Exception.Message -ne 'UNRECOGNIZED_OFFICIAL_RESPONSE'){throw}}
    Write-Output 'PASS: official ProjectID/ResultID XML fields; unsafe HTML rejected'
    exit 0
}
Write-Output 'NTIS R&D patent project-number INDEX CONTROL TEST'
Write-Output 'Checks whether a project ID from a proven official rpatent HIT can be searched again.'
Write-Output '6 requests maximum. Only counts and booleans are exported, no unrelated HIT details.'
$key=$null;$secret=$null
if($OfflineTest){$key='SYNTHETIC_KEY_NEVER_SENT'}
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
    $phase='KNOWN_POSITIVE_SEED'
    $checks=New-Object System.Collections.ArrayList
    $seed=Query-Official '' $seedTerm 'DBT=PAT' $key 'seed'
    $seedHits=[long]$seed.totalHits
    $seedRows=@($seed.rows).Count
    $control=$null
    foreach($hit in @($seed.rows)){
        if($hit.projectId -match '^\d{10}$' -and $hit.resultId -match '^[A-Za-z0-9_-]{5,100}$'){
            $control=$hit;break
        }
    }
    $seedGood=($null -ne $control)
    $runs=New-Object System.Collections.ArrayList
    if($seedGood){
        $phase='VERIFY_ACTUAL_OFFICIAL_PROJECTID_INDEX'
        $p=[string]$control.projectId
        $testCases=@(
            [pscustomobject]@{mode='project_ti';field='TI';query=$p;filter='DBT=PAT'},
            [pscustomobject]@{mode='project_bi';field='BI';query=$p;filter='DBT=PAT'},
            [pscustomobject]@{mode='project_unscoped';field='';query=$p;filter='DBT=PAT'},
            [pscustomobject]@{mode='ti03_seed';field='';query=$seedTerm;filter=('TI03='+$p+'&DBT=PAT')},
            [pscustomobject]@{mode='ti03_project';field='TI';query=$p;filter=('TI03='+$p+'&DBT=PAT')}
        )
        foreach($q in $testCases){
            try{
                $response=Query-Official $q.field $q.query $q.filter $key $q.mode
                [void]$runs.Add((Summary $response $p ([string]$control.resultId) $q.mode))
                $last=$runs[$runs.Count-1]
                Write-Output ('CHECK '+$q.mode+': total='+$last.totalHits+
                    ' scanned='+$last.rowsInspected+
                    ' exactReferenceOutcomeInFirstPage='+$last.exactReferenceOutcomeRows)
            }catch{
                $reason=[string]$_.Exception.Message
                $accepted=@('NTIS_NETWORK_OR_APPROVAL_ERROR','NTIS_HTTP_401',
                    'NTIS_HTTP_403','NTIS_HTTP_404','UNSAFE_SOURCE_XML','BAD_OFFICIAL_XML',
                    'UNRECOGNIZED_OFFICIAL_RESPONSE','INDEX_HITS_WITHOUT_RECORDS',
                    'UNEXPECTED_PAGE_SIZE','UNEXPECTED_QUERY_PARAMETERS')
                $code=if($reason -in $accepted){$reason}else{'NTIS_CONTROL_QUERY_ERROR'}
                [void]$runs.Add((ErrorSummary $q.mode $code))
                Write-Output ('CHECK '+$q.mode+': error='+$code)
                if($code -in @('NTIS_HTTP_401','NTIS_HTTP_403','NTIS_HTTP_404')){break}
            }
        }
    }
    $successful=@($runs.ToArray()|Where-Object {$_.status -eq 'checked'}).Count
    $errors=@($runs.ToArray()|Where-Object {$_.status -eq 'source_error'}).Count
    $recovered=@($runs.ToArray()|Where-Object {$_.exactReferenceOutcomeRows -gt 0}).Count
    $state=if(!$seedGood){'control_unavailable'}elseif($errors){'partial_errors'}elseif($recovered -gt 0){'some_project_search_paths_work'}else{'project_id_retrieval_not_verified'}
    $now=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $data=[ordered]@{
        generatedAt=$now
        profile='ntis_rpatent_project_id_index_control_v1'
        collectionMethod='approved_pc_official_rpatent_field_control'
        status=$state
        controlSeedTerm=$seedTerm
        controlSeedTotalHits=$seedHits
        controlSeedRowsInspected=$seedRows
        officialReferenceProjectAndOutcomeSeenInSeed=$seedGood
        controlProjectIdExported=$false
        controlResultIdExported=$false
        plannedAdditionalControlQueries=5
        completedAdditionalControlQueries=$successful
        failedAdditionalControlQueries=$errors
        exactReferenceOutcomeRecoveredInAnyMode=($recovered -gt 0)
        searchModes=@($runs.ToArray())
        verifiedPatentProjectOutcomeLinks=0
        commercializationConfirmed=0
        exclusiveConfirmed=0
        warning='An official positive-control rpatent ProjectID and ResultID from the same HIT are queried under TI, BI, unscoped and TI03 variants. Neither TOTALHITS>0 nor recovery within first 10 proves project field has full coverage; 0 is not evidence of no national R&D patent. No private unrelated outcome row is saved.'
    }
    $json=$data|ConvertTo-Json -Depth 12
    if($json.Contains($key) -or $json -match '(?i)apprvKey|authorization|bearer\s'){
        throw 'CREDENTIAL_EXPOSURE_ABORTED'
    }
    if($seedGood){
        if($json.Contains([string]$control.projectId) -or
           $json.Contains([string]$control.resultId)){throw 'CONTROL_ID_LEAK_ABORTED'}
    }
    [System.IO.File]::WriteAllText($outFile,$json+[Environment]::NewLine,(New-Object System.Text.UTF8Encoding($false)))
    Write-Output ('RESULT: '+$state+'; controlSeedHits='+$seedHits+
        '; modesCompleted='+$successful+'/5; referenceOutcomeRecoveredPaths='+$recovered)
    Write-Output 'OUTPUT_FILE: ntis_project_field_probe_pc_latest.json'
    if($OfflineTest){
        if($state -ne 'some_project_search_paths_work' -or $successful -ne 5 -or
           $recovered -ne 3 -or $data.searchModes[0].exactReferenceOutcomeRows -ne 0){
            throw 'OFFLINE_INDEX_CONTROL_FAILED'
        }
        if(!$KeepOfflineOutput){Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue}
        Write-Output 'PASS: real official-XML control reference and 5 synthetic search-field paths; no unrelated IDs exported'
    }
}catch{
    $type=$_.Exception.GetType().Name -replace '[^A-Za-z0-9]',''
    $line=[int]$_.InvocationInfo.ScriptLineNumber
    $phaseName=if($phase -in @('KNOWN_POSITIVE_SEED','VERIFY_ACTUAL_OFFICIAL_PROJECTID_INDEX')){$phase}else{'UNSPECIFIED'}
    Write-Output 'RESULT: NTIS_INDEX_CONTROL_FAILED'
    Write-Output ('DIAGNOSTIC: PHASE='+$phaseName+' TYPE='+$type+' LINE='+$line)
    if($OfflineTest){Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue}
    exit 2
}finally{$key=$null;$secret=$null}
