# NTIS patent outcome (성과검색 전체용) schema check from approved Windows PC.
# CAUTION: public_result is a candidate endpoint from public integration
# examples. The user's OFFICIAL outcome-search manual and approval are still
# required. This tool exports XML FIELD NAMES only: no record contents/keys.
param([switch]$SelfTest)

$ErrorActionPreference='Stop'
$api='https://www.ntis.go.kr/rndopen/openApi/public_result'
$file=Join-Path $PSScriptRoot 'ntis_patent_outcome_schema_probe.json'

function MakeUri([string]$query,[string]$key){
    $args=[ordered]@{
        apprvKey=$key;userId='';collection='rpatent'
        SRWR=$query;searchFd='BI';addQuery='DBT=PAT'
        startPosition='1';displayCnt='3'
    }
    $tokens=@(foreach($x in $args.GetEnumerator()){
        [Uri]::EscapeDataString([string]$x.Key)+'='+[Uri]::EscapeDataString([string]$x.Value)
    })
    return $api+'?'+($tokens -join '&')
}

function ProbeXml([string]$payload){
    if(!$payload -or $payload.Length -gt 800000 -or $payload -match '(?i)<!DOCTYPE|<!ENTITY'){
        throw 'OUTCOME_XML_INVALID'
    }
    $doc=New-Object System.Xml.XmlDocument
    $doc.XmlResolver=$null
    try{$doc.LoadXml($payload)}catch{throw 'OUTCOME_XML_INVALID'}
    if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'OUTCOME_XML_SCHEMA_UNRECOGNIZED'}
    $num=$doc.SelectSingleNode('/RESULT/TOTALHITS')
    $items=$doc.SelectSingleNode('/RESULT/RESULTSET')
    if($null -eq $num -or $null -eq $items -or $num.InnerText -notmatch '^\d{1,10}$'){
        throw 'OUTCOME_XML_SCHEMA_UNRECOGNIZED'
    }
    $hits=@($doc.SelectNodes('/RESULT/RESULTSET/HIT'))
    if([long]$num.InnerText -gt 0 -and $hits.Count -eq 0){
        throw 'OUTCOME_TOTAL_WITH_NO_ROWS'
    }
    $paths=New-Object System.Collections.ArrayList
    if($hits.Count -gt 0){
        $queue=New-Object System.Collections.Queue
        $queue.Enqueue([pscustomobject]@{node=$hits[0];path='HIT';depth=0})
        while($queue.Count -gt 0 -and $paths.Count -lt 100){
            $current=$queue.Dequeue()
            if($current.depth -gt 4){continue}
            foreach($child in $current.node.ChildNodes){
                if($child.NodeType -ne [System.Xml.XmlNodeType]::Element){continue}
                $p=$current.path+'/'+$child.LocalName
                if(!$paths.Contains($p)){[void]$paths.Add($p)}
                $queue.Enqueue([pscustomobject]@{node=$child;path=$p;depth=($current.depth+1)})
            }
        }
    }
    return [pscustomobject]@{
        totalHits=[long]$num.InnerText
        sampleHitCount=$hits.Count
        fieldPaths=@($paths.ToArray() | Sort-Object -Unique)
    }
}

if($SelfTest){
    $test=MakeUri -query '1020250039383' -key 'TEST_KEY'
    if($test -notmatch 'collection=rpatent' -or $test -notmatch 'addQuery=DBT%3DPAT' -or
       $test -notmatch 'SRWR=1020250039383' -or $test -notmatch 'apprvKey=TEST_KEY'){
        throw 'OUTCOME_REQUEST_SELFTEST_FAILED'
    }
    $mock='<RESULT><TOTALHITS>1</TOTALHITS><RESULTSET><HIT><ResultId>PTO-1</ResultId><Patent><ApplicationNo>10-2025-0039383</ApplicationNo></Patent><Project><Id>123</Id></Project></HIT></RESULTSET></RESULT>'
    $r=ProbeXml -payload $mock
    if($r.totalHits -ne 1 -or $r.fieldPaths -notcontains 'HIT/Patent/ApplicationNo' -or
       $r.fieldPaths -notcontains 'HIT/Project/Id'){throw 'OUTCOME_XML_SELFTEST_FAILED'}
    try{
        [void](ProbeXml -payload '<html>Access denied</html>')
        throw 'OUTCOME_SCHEMA_FAIL_OPEN'
    }catch{
        if($_.Exception.Message -ne 'OUTCOME_XML_SCHEMA_UNRECOGNIZED'){throw}
    }
    Write-Output 'PASS: NTIS outcome request profile, XML schema-only parsing and invalid XML rejection'
    exit 0
}

Write-Output 'NTIS patent outcome field-name probe'
Write-Output 'Separate NTIS outcome-search approval may be required.'
Write-Output 'This reads XML element names ONLY. No patent/organization/individual data or key is saved.'
$secure=Read-Host 'Enter approved NTIS key (hidden)' -AsSecureString
$ptr=[IntPtr]::Zero;$key=$null
try{
    $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
}finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
if([string]::IsNullOrWhiteSpace($key)){Write-Output 'RESULT: MISSING_KEY';exit 2}

$reports=New-Object System.Collections.ArrayList
$queries=@('1020250039383',(-join @([char]0xBD80,[char]0xBD84,[char]0xBC29,[char]0xC804)))
$overall='not_yet_verified'
try{
    foreach($query in $queries){
        $url=MakeUri -query $query -key $key
        $code=$null;$body=$null
        try{
            $r=Invoke-WebRequest -Uri $url -Method Get -UseBasicParsing -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
            $code=[int]$r.StatusCode;$body=[string]$r.Content
        }catch{
            if($null -ne $_.Exception.Response){
                try{$code=[int]$_.Exception.Response.StatusCode}catch{$code=$null}
            }
            if($null -eq $code){$code='network_or_access_error'}
        }finally{$url=$null}
        if($code -ne 200){
            $label=if($code -is [int]){'HTTP_'+$code}else{[string]$code}
            [void]$reports.Add([pscustomobject]@{searchType='candidate_number_or_technology';status=$label})
            Write-Output ('QUERY: '+$label)
            if($code -in @(401,403,404)){break}
            continue
        }
        try{
            $parsed=ProbeXml -payload $body
            $label=if($parsed.sampleHitCount -gt 0){'outcome_rows_schema_observed_unmapped'}else{'valid_empty_result_not_proof'}
            if($parsed.sampleHitCount -gt 0){$overall='outcome_xml_field_names_ready_for_official_manual_check'}
            [void]$reports.Add([pscustomobject]@{
                searchType='candidate_number_or_technology'
                status=$label
                totalHits=$parsed.totalHits
                sampleHitCount=$parsed.sampleHitCount
                fieldPaths=@($parsed.fieldPaths)
            })
            Write-Output ('QUERY: '+$label+'; total='+$parsed.totalHits+'; fields='+$parsed.fieldPaths.Count)
            if($parsed.sampleHitCount -gt 0){break}
        }catch{
            $label=[string]$_.Exception.Message
            if($label -notin @('OUTCOME_XML_INVALID','OUTCOME_XML_SCHEMA_UNRECOGNIZED','OUTCOME_TOTAL_WITH_NO_ROWS')){
                $label='OUTCOME_SCHEMA_ERROR'
            }
            [void]$reports.Add([pscustomobject]@{searchType='candidate_number_or_technology';status=$label})
            Write-Output ('QUERY: '+$label)
            break
        }finally{$body=$null}
    }
    $data=[ordered]@{
        generatedAt=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
        status=$overall
        endpointCandidate='/rndopen/openApi/public_result'
        approvedServiceConfirmed=$false
        fieldMappingVerified=$false
        outcomeProjectPatentLinksConfirmed=0
        privacy='Only XML field PATHS, no record values or key'
        results=@($reports.ToArray())
    }
    $json=$data | ConvertTo-Json -Depth 8
    if($json.Contains($key)){throw 'UNSAFE_OUTCOME_EXPORT_ABORTED'}
    [System.IO.File]::WriteAllText($file,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
    Write-Output ('RESULT: '+$overall)
    Write-Output 'OUTPUT_FILE: ntis_patent_outcome_schema_probe.json'
    Write-Output 'Send this JSON file and the official outcome-search API PDF manual, NOT your NTIS key.'
}catch{
    Write-Output 'RESULT: OUTCOME_DIAGNOSTIC_FAILED_NO_KEY_LOGGED'
    exit 2
}finally{$key=$null;$secure=$null}
