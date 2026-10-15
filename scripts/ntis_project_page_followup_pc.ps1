# NTIS approved-PC single missing-page replay. Live requests: page 1 + page 2 only.
# The 2026-10-15 23-project source searched only first 10/11 rows for 1415180715.
# Never publish unrelated HIT identifiers, personal information, keys or URLs.
param(
  [switch]$OfflineTest,
  [switch]$SelfTest,
  [string]$SnapshotRoot='',
  [string]$SnapshotCommit=''
)
$ErrorActionPreference='Stop'
$target='1415180715'
$sourceTime='2026-10-15T10:52:32+09:00'
$profile='ntis_rpatent_single_project_page_followup_v1'
$phase='INITIAL'
if($SnapshotCommit -and $SnapshotCommit -notmatch '^[0-9a-fA-F]{40}$'){throw 'INVALID_SOURCE_COMMIT'}
$ref=if($SnapshotCommit){$SnapshotCommit}else{'main'}
$base='https://raw.githubusercontent.com/shhong9173-art/seoul-reporting-radar/'+$ref+'/'
$endpoint='https://www.ntis.go.kr/rndopen/openApi/public_result'
$out=Join-Path $PSScriptRoot 'ntis_project_page_followup_pc_latest.json'
if($OfflineTest){
  if(!$SnapshotRoot){throw 'OFFLINE_SNAPSHOT_ROOT_REQUIRED'}
  $out=Join-Path ([System.IO.Path]::GetTempPath()) 'ntis_project_page_followup_offline.json'
}
function Load-Source([string]$path){
  try{
    if($OfflineTest){
      $full=Join-Path $SnapshotRoot ($path -replace '/',[System.IO.Path]::DirectorySeparatorChar)
      return ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($full,[Text.Encoding]::UTF8))
    }
    $r=Invoke-WebRequest -Uri ($base+$path) -TimeoutSec 25 -UseBasicParsing -MaximumRedirection 0
    if([int]$r.StatusCode -ne 200 -or $r.Content.Length -gt 800000){throw 'SOURCE_INVALID'}
    return ConvertFrom-Json -InputObject ([string]$r.Content)
  }catch{throw 'SOURCE_FETCH_FAILED'}
}
function Parse-Result([string]$body){
  if(!$body -or $body.Length -gt 1500000 -or $body -match '(?i)<!DOCTYPE|<!ENTITY'){
    throw 'INVALID_OFFICIAL_XML'
  }
  $doc=New-Object Xml.XmlDocument
  $doc.XmlResolver=$null
  try{$doc.LoadXml($body)}catch{throw 'INVALID_OFFICIAL_XML'}
  if($doc.DocumentElement.LocalName -ne 'RESULT'){throw 'INVALID_OFFICIAL_RESULT'}
  $hits=$doc.SelectSingleNode('/RESULT/TOTALHITS')
  $set=$doc.SelectSingleNode('/RESULT/RESULTSET')
  if($null -eq $hits -or $null -eq $set -or $hits.InnerText -notmatch '^\d{1,8}$'){
    throw 'UNVERIFIED_RESULT_SCHEMA'
  }
  $rows=New-Object Collections.ArrayList
  foreach($h in $doc.SelectNodes('/RESULT/RESULTSET/HIT')){
    $type=$h.SelectSingleNode('RegistType')
    $value={param($name,$max) $n=$h.SelectSingleNode($name);if($null -eq $n){return ''}
      $s=[string]$n.InnerText;$s=[regex]::Replace($s,'\s+',' ').Trim()
      if($s.Length -gt $max){$s=$s.Substring(0,$max)};return $s}
    [void]$rows.Add([pscustomobject]@{
      projectId=(& $value 'ProjectID' 30)
      resultId=(& $value 'ResultID' 100)
      registNumber=(& $value 'RegistNumber' 80)
      registType=(& $value 'RegistType' 30)
      registCode=if($null -ne $type){[string]$type.GetAttribute('code')}else{''}
      resultTitle=(& $value 'ResultTitle' 180)
    })
  }
  if($rows.Count -gt 10){throw 'INVALID_PAGE_SIZE'}
  return [pscustomobject]@{total=[long]$hits.InnerText;rows=@($rows.ToArray())}
}
function Get-Page([int]$start,[string]$key){
  if($OfflineTest){
    $hits=New-Object Collections.ArrayList
    if($start -eq 1){
      for($i=0;$i -lt 10;$i++){
        [void]$hits.Add('<HIT><ProjectID>'+$target+'</ProjectID><ResultID>MOCKPAGE'+$i+'A</ResultID><RegistType code="02">등록</RegistType><RegistNumber>10-2015-0000001</RegistNumber></HIT>')
      }
    }else{
      [void]$hits.Add('<HIT><ProjectID>'+$target+'</ProjectID><ResultID>MOCKPAGE11B</ResultID><RegistType code="01">출원</RegistType><RegistNumber>10-2025-0039383</RegistNumber><ResultTitle>TEST_ONLY</ResultTitle></HIT>')
    }
    return Parse-Result ('<RESULT><TOTALHITS>11</TOTALHITS><RESULTSET>'+(@($hits.ToArray()) -join '')+'</RESULTSET></RESULT>')
  }
  if($start -notin @(1,11)){throw 'UNAPPROVED_PAGE'}
  $params=[ordered]@{
    naviCount='30';searchField='TI';addQuery='DBT=PAT';query=$target
    displayCount='10';sortby='';collection='rpatent';boostquery=''
    userId='';startPosition=[string]$start;apprvKey=$key;cmbnApiYn='Y'
  }
  $query=@(foreach($p in $params.GetEnumerator()){
    [Uri]::EscapeDataString([string]$p.Key)+'='+[Uri]::EscapeDataString([string]$p.Value)
  }) -join '&'
  $uri=$endpoint+'?'+$query
  try{
    $r=Invoke-WebRequest -Uri $uri -UseBasicParsing -Method Get -TimeoutSec 25 -MaximumRedirection 0 -ErrorAction Stop
    if([int]$r.StatusCode -ne 200){throw 'NTIS_HTTP_FAILED'}
    return Parse-Result ([string]$r.Content)
  }catch{throw 'NTIS_PAGE_REQUEST_FAILED'}finally{$uri=$null;$query=$null}
}
if($SelfTest){
  $p=Get-Page 1 'TEST_ONLY'
  $q=Get-Page 11 'TEST_ONLY'
  if(!$OfflineTest -or $p.rows.Count -ne 10 -or $q.rows.Count -ne 1 -or
     $q.rows[0].resultId -ne 'MOCKPAGE11B'){throw 'SELFTEST_FAILED'}
  Write-Output 'PASS: 10+1 synthetic XML page decoding'
  exit 0
}
$key=$null;$secret=$null
try{
  $phase='VERIFY_HISTORICAL_SOURCES'
  $plan=Load-Source 'digests/ntis_project_reverse_plan_latest.json'
  $original=Load-Source 'digests/ntis_project_reverse_remaining_23_pc_latest.json'
  $kipris=Load-Source 'digests/ntis_project_reverse_kipris_source.json'
  if($plan.planVersion -ne 'ntis_rpatent_reverse_projectid_v1' -or
     $plan.projectCount -ne 26 -or
     $original.generatedAt -ne $sourceTime -or
     $original.planGeneratedAt -ne $plan.generatedAt -or
     $original.plannedUniqueProjects -ne 23 -or
     $original.completedProjects -ne 23 -or
     $original.failedProjects -ne 0 -or
     $original.reviewedNumberPairs -ne 0 -or
     $kipris.schema -ne 'ntis_rpatent_kipris_7_identifiers_frozen_v1' -or
     $kipris.confirmedProjectOutcomeLinks -ne 0){throw 'SOURCE_SNAPSHOT_CHANGED'}
  $expected=@($plan.projects|Where-Object {$_.projectNumber -eq $target})
  $prior=@($original.checks|Where-Object {$_.projectNumber -eq $target})
  if($expected.Count -ne 1 -or $prior.Count -ne 1 -or
     $prior[0].primaryTotalHits -ne 11 -or
     $prior[0].rowsInspected -ne 10 -or
     $prior[0].uninspectedPagesRemain -ne $true -or
     $prior[0].matchingKiprisApplicationRows -ne 0 -or
     @($original.checks|Where-Object {$_.uninspectedPagesRemain}).Count -ne 1){
    throw 'NOT_EXACTLY_ONE_SOURCE_PAGE_GAP'
  }
  $apps=@{}
  foreach($t in @($plan.targetKiprisApplications)){
    $pub=[string]$t.publicationNumber
    $app=[string]$t.applicationNumber
    if($pub -notmatch '^10\d{11}$' -or $app -notmatch '^10\d{11}$'){throw 'INVALID_KIPRIS_SOURCE'}
    if(!$apps.ContainsKey($app)){$apps[$app]=New-Object Collections.ArrayList}
    [void]$apps[$app].Add($pub)
  }
  if(@($plan.targetKiprisApplications).Count -ne 7){throw 'CHANGED_KIPRIS_TARGET_POPULATION'}
  if(!$OfflineTest){
    $secret=Read-Host 'Approved NTIS rpatent key (hidden)' -AsSecureString
    $ptr=[IntPtr]::Zero
    try{
      $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
      $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    }finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}}
    if([string]::IsNullOrWhiteSpace($key)){throw 'MISSING_APPROVED_KEY'}
  }else{$key='OFFLINE_TEST_ONLY'}
  $phase='RECHECK_BOTH_OFFICIAL_PAGES'
  $first=Get-Page 1 $key
  $second=Get-Page 11 $key
  if($first.total -ne 11 -or $second.total -ne 11 -or
     @($first.rows).Count -ne 10 -or @($second.rows).Count -ne 1){
    throw 'INDEX_CHANGED_OR_UNVERIFIED_PAGINATION'
  }
  $all=@($first.rows)+@($second.rows)
  $seen=New-Object 'System.Collections.Generic.HashSet[string]'
  foreach($row in $all){
    if($row.resultId -notmatch '^[A-Za-z0-9_-]{5,100}$' -or
       !$seen.Add($row.resultId)){throw 'PAGE_REPEAT_OR_RESULT_ID_MISSING'}
  }
  $matched=New-Object Collections.ArrayList
  foreach($row in $all){
    if($row.projectId -ne $target -or $row.registCode -ne '01' -or $row.registType -ne '출원'){continue}
    $app=([string]$row.registNumber -replace '[\s-]','')
    if($app -notmatch '^10\d{11}$' -or !$apps.ContainsKey($app)){continue}
    foreach($pub in @($apps[$app].ToArray())){
      [void]$matched.Add([pscustomobject]@{
        projectNumber=$target;publicationNumber=$pub;applicationNumber=$app
        officialResultID=$row.resultId;sourceProjectID=$row.projectId
        sourceRegistType='출원';sourceRegistTypeCode='01'
        sourceRegistNumber=$row.registNumber;resultTitle=$row.resultTitle
        sameOfficialHitIdentifiers=$true
        officialPatentProjectOutcomeVerified=$false
        commercializationConfirmed=$false;exclusiveConfirmed=$false
      })
    }
  }
  $now=[DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(9)).ToString('yyyy-MM-ddTHH:mm:sszzz')
  $export=[ordered]@{
    profile=$profile;generatedAt=$now
    sourceReverseGeneratedAt=$sourceTime;planGeneratedAt=[string]$plan.generatedAt
    projectNumber=$target
    status='ready'
    collectionMethod=if($OfflineTest){'offline_synthetic_test_not_real'}else{'approved_pc_ntis_rpatent_targeted_page_followup'}
    offlineSynthetic=[bool]$OfflineTest
    queryMode='primary';pageSize=10
    currentQueryTotalHits=11;firstPageRows=10;secondPageRows=1
    rowsInspected=11;actualHttpRequests=2;maxHttpRequests=2
    distinctResultIDs=11;paginationConfirmedByDisjointIds=$true
    currentQueryFullyInspected=$true
    matchedOfficialProjectApplicationRows=$matched.Count
    records=@($matched.ToArray())
    verifiedPatentProjectOutcomes=0
    confirmedCommercialization=0;confirmedExclusives=0
    warning='Two fresh pages inspected with 11 distinct ResultIDs; historical 10 row identifiers were not preserved, so equality of historical HIT identities is not established. Zero matching pairs does not prove absence. Matching pair is review only, never commercialization, company participation or scoop.'
  }
  $json=$export|ConvertTo-Json -Depth 12
  if($json.Contains($key) -or $json -match '(?i)apprvKey|authorization|bearer\s|api[_-]?key|password|secret'){
    throw 'OUTPUT_FAILED_SECURITY_CHECK'
  }
  [IO.File]::WriteAllText($out,$json+[Environment]::NewLine,([System.Text.UTF8Encoding]::new($false)))
  Write-Output ('RESULT: ready; official calls 2/2; pages 1+2; observed 11 distinct rows; exact KIPRIS number-pair review leads '+$matched.Count)
  Write-Output ('OUTPUT_FILE: '+(Split-Path $out -Leaf))
}catch{
  # No raw exception or URL: .NET exceptions may contain the secret-bearing URL.
  Write-Output ('RESULT: FAILED_SAFELY; PHASE='+$phase)
  if($OfflineTest){Remove-Item -LiteralPath $out -Force -ErrorAction SilentlyContinue}
  exit 2
}finally{$key=$null;$secret=$null}
