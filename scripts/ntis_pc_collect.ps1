# NTIS approved-PC R&D collector (Windows PowerShell 5.1+).
# Key is requested securely, transmitted only to NTIS, never saved.
param([switch]$SelfTest,[ValidateRange(1,12)][int]$MaxQueries=8)
$ErrorActionPreference='Stop'
$api='https://www.ntis.go.kr/rndopen/openApi/public_project'
$source='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/main/digests/patent_rnd_dossiers_latest.json'
$outputFile=Join-Path $PSScriptRoot 'ntis_project_leads_latest.json'

function TrimText($node,[int]$limit) {
    if($null -eq $node){return $null}
    $s=[regex]::Replace([string]$node.InnerText,'\s+',' ').Trim()
    if($s.Length -gt $limit){$s=$s.Substring(0,$limit)}
    if(!$s){return $null};return $s
}
function Get-OfficialProjects([string]$xml,[int]$maxRows) {
    if(!$xml -or $xml.Length -gt 1500000 -or $xml -match '(?i)<!DOCTYPE|<!ENTITY'){throw 'NTIS_INVALID_XML'}
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($xml)}catch{throw 'NTIS_XML_PARSE_ERROR'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'NTIS_SCHEMA_UNKNOWN'}
    $tot=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $tot -or $null -eq $set -or $tot.InnerText -notmatch '^\d{1,10}$'){throw 'NTIS_SCHEMA_UNKNOWN'}
    $total=[long]$tot.InnerText
    $hits=@($doc.SelectNodes('/RESULT/RESULTSET/HIT'))
    if($total -gt 0 -and $hits.Count -eq 0){throw 'NTIS_NO_PROJECT_ROWS'}
    $rows=New-Object System.Collections.ArrayList
    foreach($hit in ($hits | Select-Object -First $maxRows)){
        $id=TrimText ($hit.SelectSingleNode('ProjectNumber')) 80
        $title=TrimText ($hit.SelectSingleNode('ProjectTitle/Korean')) 200
        if(!$title){$title=TrimText ($hit.SelectSingleNode('ProjectTitle/English')) 200}
        if(!$id -or !$title){throw 'NTIS_PROJECT_FIELDS_UNKNOWN'}
        [void]$rows.Add([pscustomobject]@{
            projectNumber=$id;projectTitle=$title
            performingAgency=(TrimText ($hit.SelectSingleNode('ResearchAgency/Name')) 90)
            projectYear=(TrimText ($hit.SelectSingleNode('ProjectYear')) 6)
            periodStart=(TrimText ($hit.SelectSingleNode('ProjectPeriod/Start')) 20)
            periodEnd=(TrimText ($hit.SelectSingleNode('ProjectPeriod/End')) 20)
            researchSummary=(TrimText ($hit.SelectSingleNode('Abstract/Teaser')) 240)
            keyword=(TrimText ($hit.SelectSingleNode('Keyword/Korean')) 140)
            sourceSearchUrl=('https://www.ntis.go.kr/ThSearchProjectList.do?dbt=project&searchWord='+[Uri]::EscapeDataString($id))
            researchLinkConfirmed=$false;patentOutcomeConfirmed=$false
            companyProjectParticipationConfirmed=$false;commercializationConfirmed=$false
        })
    }
    return [pscustomobject]@{totalHits=$total;firstPageOnly=($total -gt $hits.Count);records=@($rows.ToArray())}
}
function Invoke-Ntis([string]$term,[string]$key,[int]$count){
    if($term.Length -lt 2 -or $term.Length -gt 110){throw 'INVALID_QUERY'}
    $parts=[ordered]@{
        naviCount='30';searchField='';addQuery='';query=$term
        displayCount=[string]$count;sortby='';collection='project'
        boostquery='';userId='';startPosition='1';apprvKey=$key;cmbnApiYn='Y'
    }
    $tokens=@(foreach($p in $parts.GetEnumerator()){
        [Uri]::EscapeDataString([string]$p.Key)+'='+[Uri]::EscapeDataString([string]$p.Value)
    })
    $url=$api+'?'+($tokens -join '&')
    $code=$null;$body=$null
    try{
        $response=Invoke-WebRequest -Uri $url -UseBasicParsing -Method Get -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
        $code=[int]$response.StatusCode;$body=[string]$response.Content
    }catch{
        if($null -ne $_.Exception.Response){
            try{$code=[int]$_.Exception.Response.StatusCode}catch{$code=$null}
        }
        if($null -eq $code){throw 'NTIS_NETWORK_OR_ACCESS_ERROR'}
    }finally{$url=$null}
    if($code -ne 200){throw ('NTIS_HTTP_'+$code)}
    return Get-OfficialProjects -xml $body -maxRows $count
}
if($SelfTest){
    $mock='<RESULT><TOTALHITS>2</TOTALHITS><RESULTSET><HIT><ProjectNumber>1234567890</ProjectNumber><ProjectTitle><Korean>Demo</Korean></ProjectTitle></HIT></RESULTSET></RESULT>'
    $p=Get-OfficialProjects -xml $mock -maxRows 10
    if($p.totalHits -ne 2 -or $p.records.Count -ne 1 -or !$p.firstPageOnly){throw 'SELFTEST_FAILED'}
    try{[void](Get-OfficialProjects -xml '<html>denied</html>' -maxRows 10);throw 'SELFTEST_FAIL_OPEN'}
    catch{if($_.Exception.Message -ne 'NTIS_SCHEMA_UNKNOWN'){throw}}
    Write-Output 'PASS: NTIS XML rows, invalid XML rejection and output shape'
    exit 0
}
Write-Output 'NTIS approved-PC project collection'
Write-Output 'The key is hidden and never written to output.'
$secure=Read-Host 'Enter NTIS approved API key (hidden)' -AsSecureString
$ptr=[IntPtr]::Zero;$key=$null
try{
    $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}
try{
    $nano=[string][char]0xB098+[string][char]0xB178
    $probe=Invoke-Ntis -term $nano -key $key -count 1
    if($probe.totalHits -le 0 -or $probe.records.Count -lt 1){throw 'NTIS_PROBE_NOT_VERIFIED'}
    Write-Output 'NTIS SOURCE: VERIFIED_REAL_PROJECT_ROW'
    try{
        $res=Invoke-WebRequest -Uri $source -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
        $dossier=ConvertFrom-Json -InputObject ([string]$res.Content)
    }catch{throw 'DOSSIER_DOWNLOAD_FAILED'}
    if($dossier.status -ne 'research_only' -or !$dossier.generatedAt -or $null -eq $dossier.dossiers){throw 'DOSSIER_INVALID'}
    $ranked=@($dossier.dossiers | Sort-Object -Property @{Expression={if($_.recentPatentWithin3Days){0}else{1}}},@{Expression={if($_.pressLookupCompleted){0}else{1}}},@{Expression={$_.publicationNumber}})
    $plans=New-Object System.Collections.ArrayList
    foreach($d in $ranked){
        $pub=[string]$d.publicationNumber
        if($pub -notmatch '^10\d{11}$'){continue}
        foreach($item in @($d.ntisResearchQueries) | Select-Object -First 2){
            if($null -eq $item){continue}
            $q=[string]$item.query
            if($q.Length -lt 2 -or $q.Length -gt 110){continue}
            [void]$plans.Add([pscustomobject]@{
                publicationNumber=$pub;publicationDate=[string]$d.publicationDate
                patentTitle=[string]$d.title;query=$q
            })
            if($plans.Count -ge $MaxQueries){break}
        }
        if($plans.Count -ge $MaxQueries){break}
    }
    $time=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $checks=New-Object System.Collections.ArrayList
    $errors=0
    foreach($p in $plans){
        $entry=[ordered]@{
            publicationNumber=$p.publicationNumber
            publicationDate=$p.publicationDate
            patentTitle=$p.patentTitle
            query=$p.query
            checkedAt=$time
        }
        try{
            $result=Invoke-Ntis -term $p.query -key $key -count 10
            $entry.status='checked';$entry.totalHits=$result.totalHits
            $entry.firstPageOnly=$result.firstPageOnly;$entry.records=@($result.records)
            $entry.sourceEndpointPath='/rndopen/openApi/public_project'
            Write-Output ('CHECK '+($checks.Count+1)+': total='+$result.totalHits+', rows='+$result.records.Count)
        }catch{
            $codes=@('NTIS_HTTP_404','NTIS_HTTP_401','NTIS_HTTP_403','NTIS_NETWORK_OR_ACCESS_ERROR',
                     'NTIS_INVALID_XML','NTIS_XML_PARSE_ERROR','NTIS_SCHEMA_UNKNOWN',
                     'NTIS_NO_PROJECT_ROWS','NTIS_PROJECT_FIELDS_UNKNOWN','INVALID_QUERY')
            $reason=[string]$_.Exception.Message
            if($codes -notcontains $reason){$reason='NTIS_QUERY_FAILED'}
            $entry.status='source_error';$entry.errorClass=$reason;$errors+=1
            Write-Output ('CHECK '+($checks.Count+1)+': '+$reason)
        }
        [void]$checks.Add([pscustomobject]$entry)
        if($entry.status -eq 'source_error' -and
           $entry.errorClass -in @('NTIS_HTTP_404','NTIS_HTTP_401','NTIS_HTTP_403','NTIS_SCHEMA_UNKNOWN')){break}
    }
    $done=@($checks.ToArray() | Where-Object {$_.status -eq 'checked'}).Count
    $remaining=$plans.Count - $checks.Count
    $recordCount=0
    foreach($c in $checks){if($c.status -eq 'checked'){$recordCount+=@($c.records).Count}}
    $state=if($errors){'partial_errors'}elseif(!$plans.Count){'no_queries'}elseif($remaining){'partial_not_yet_checked'}else{'ready'}
    $out=[ordered]@{
        generatedAt=$time;dossierGeneratedAt=[string]$dossier.generatedAt
        status=$state
        source='NTIS public_project OpenAPI - public project metadata'
        requestProfile='ntis_2025_pdf_page11_rest_example'
        collectionMethod='approved_pc_local_manual_review'
        scope='First search page of selected patent research queries only'
        totalResearchQueries=$plans.Count;completedQueries=$done;failedQueries=$errors
        remainingQueries=$remaining;newQueriesThisRun=$checks.Count;sourceRecords=$recordCount
        projectPatentLinksConfirmed=0;actualApplicationConfirmed=0
        checks=@($checks.ToArray())
        warning='Keyword matches are not verified project/patent links, corporate participation, commercialization, or exclusives.'
    }
    $json=$out | ConvertTo-Json -Depth 16
    if($json.Contains($key)){throw 'UNSAFE_OUTPUT_ABORTED'}
    $utf8=[System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($outputFile,$json+[Environment]::NewLine,$utf8)
    Write-Output ('RESULT: '+$state+'; searches='+$done+'; first-page records='+$recordCount)
    Write-Output 'OUTPUT_FILE: ntis_project_leads_latest.json'
    Write-Output 'Inspect JSON before uploading it to ChatGPT for review.'
}catch{
    $codes=@('NTIS_PROBE_NOT_VERIFIED','DOSSIER_DOWNLOAD_FAILED','DOSSIER_INVALID',
             'NTIS_HTTP_404','NTIS_HTTP_401','NTIS_HTTP_403','NTIS_NETWORK_OR_ACCESS_ERROR',
             'NTIS_INVALID_XML','NTIS_XML_PARSE_ERROR','NTIS_SCHEMA_UNKNOWN',
             'NTIS_NO_PROJECT_ROWS','NTIS_PROJECT_FIELDS_UNKNOWN','UNSAFE_OUTPUT_ABORTED')
    $message=[string]$_.Exception.Message
    if($codes -notcontains $message){$message='COLLECTION_FAILED'}
    Write-Output ('RESULT: '+$message)
    exit 2
}finally{$key=$null;$secure=$null}
