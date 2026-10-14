# NTIS public-project diagnostic from the PC whose public IP was registered.
# Windows PowerShell 5.1+ / PowerShell 7+. Does not save or print the API key.
# Tests the two paths printed in the official NTIS 2025 PDF; never claims
# that HTTP 404 confirms an IP block, or that a failed call means zero projects.
param([switch]$SelfTest)

$ErrorActionPreference = 'Stop'
$officialEndpoints = @(
    'https://www.ntis.go.kr/rndopen/openApi/public_project',
    'https://www.ntis.go.kr/rndopen/openApi/pjtSearch/'
)

function New-NtisRequestUri {
    param(
        [Parameter(Mandatory=$true)][string]$Endpoint,
        [Parameter(Mandatory=$true)][string]$Query,
        [Parameter(Mandatory=$true)][string]$Key,
        [ValidateSet('Example','Specification')][string]$Profile='Example'
    )
    # NTIS official 2025 PDF p.11 REST example. Its p.6 request table
    # lists alternative names (SRWR/displayCnt); do not silently mix them.
    $fields = [ordered]@{
        naviCount='30'
        searchField=''
        addQuery=''
        query=$Query
        displayCount='1'
        sortby=''
        collection='project'
        boostquery=''
        userId=''
        startPosition='1'
        apprvKey=$Key
        cmbnApiYn='Y'
    }
    if ($Profile -eq 'Specification') {
        # NTIS 2025 PDF pp.6-8 request-table wire names.
        # Kept separate from p.11 REST URI example for diagnosis of zero hits.
        $fields = [ordered]@{
            apprvKey=$Key
            userId=''
            collection='project'
            SRWR=$Query
            searchFd='BI'
            addQuery=''
            searchRnkn='DATE/DESC'
            startPosition='1'
            displayCnt='1'
        }
    }
    $pairs = foreach ($item in $fields.GetEnumerator()) {
        '{0}={1}' -f ([Uri]::EscapeDataString([string]$item.Key)),
                     ([Uri]::EscapeDataString([string]$item.Value))
    }
    return $Endpoint + '?' + ($pairs -join '&')
}

if ($SelfTest) {
    foreach ($endpoint in $officialEndpoints) {
        $uri = New-NtisRequestUri -Endpoint $endpoint -Query '나노' -Key 'DUMMY_LOCAL_TEST'
        $parts = [Uri]$uri
        if ($parts.Scheme -ne 'https' -or
            $parts.Host -ne 'www.ntis.go.kr' -or
            $parts.Query -notmatch 'collection=project' -or
            $parts.Query -notmatch 'query=%EB%82%98%EB%85%B8' -or
            $parts.Query -notmatch 'cmbnApiYn=Y' -or
            $parts.Query -notmatch 'displayCount=1') {
            throw 'Self-test: incorrect official query URL'
        }
    }
    $spec = New-NtisRequestUri -Endpoint $officialEndpoints[0] -Query '나노' -Key 'DUMMY_LOCAL_TEST' -Profile Specification
    $specParts = [Uri]$spec
    if ($specParts.Query -notmatch 'SRWR=%EB%82%98%EB%85%B8' -or
        $specParts.Query -notmatch 'searchFd=BI' -or
        $specParts.Query -notmatch 'displayCnt=1' -or
        $specParts.Query -match '(?:[?&])query=' -or
        $specParts.Query -match 'cmbnApiYn=Y') {
        throw 'Self-test: incorrect specification-table parameter profile'
    }
    Write-Output 'PASS: official NTIS paths, both documented parameter profiles and UTF-8 encoding'
    exit 0
}

Write-Output 'NTIS registered-PC diagnostic (2025 official manual)'
Write-Output 'The key is not printed or saved; it is transmitted only to NTIS over HTTPS.'
Write-Output 'Compare your CURRENT PC public IP with the address registered on NTIS.'
$secureKey = Read-Host 'Enter approved NTIS API key (hidden)' -AsSecureString
$pointer = [IntPtr]::Zero
$key = $null
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
if ([string]::IsNullOrWhiteSpace($key)) {
    Write-Output 'RESULT: no key entered; not tested.'
    exit 2
}

$verified = $false
$index = 0
try {
    foreach ($endpoint in $officialEndpoints) {
        $index += 1
        $uri = New-NtisRequestUri -Endpoint $endpoint -Query '나노' -Key $key
        $label = 'DOCUMENTED_PATH_' + $index
        $code = $null
        $content = $null
        try {
            # Reject redirects: a redirect must not be confused with a valid
            # NTIS RESULT XML (nor should the approved key be redirected).
            $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -Method Get -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
            $code = [int]$response.StatusCode
            $content = [string]$response.Content
        }
        catch {
            # Do not print the exception message, request URL or response body:
            # these may contain the key or personally identifying details.
            $remote = $_.Exception.Response
            if ($null -ne $remote) {
                try { $code = [int]$remote.StatusCode } catch { $code = $null }
            }
            if ($null -eq $code) {
                Write-Output ($label + ': NETWORK_OR_OTHER_ERROR')
                break
            }
        }
        finally {
            $uri = $null
        }

        if ($code -ne 200) {
            Write-Output ($label + ': HTTP_' + $code)
            # Probe p.4's separately documented service URL ONLY if the
            # explicit p.6 END POINT returned HTTP 404.
            if ($code -eq 404 -and $index -eq 1) { continue }
            break
        }
        if (!$content -or $content.Length -gt 1500000 -or
            $content -match '(?i)<!DOCTYPE|<!ENTITY') {
            Write-Output ($label + ': HTTP_200_BUT_INVALID_XML')
            break
        }
        try {
            [xml]$document = $content
            if ($document.DocumentElement.LocalName -ne 'RESULT') {
                throw 'Unexpected root'
            }
            $total = [string]$document.RESULT.TOTALHITS
            $resultset = $document.DocumentElement.SelectSingleNode('RESULTSET')
            if ($total -notmatch '^\d+$' -or $null -eq $resultset) {
                throw 'Unrecognized data schema'
            }
            $hits = $document.DocumentElement.SelectNodes('RESULTSET/HIT')
            if ([long]$total -gt 0 -and $null -ne $hits -and $hits.Count -gt 0) {
                $firstHit = $document.DocumentElement.SelectSingleNode('RESULTSET/HIT')
                if ($null -eq $firstHit.SelectSingleNode('ProjectNumber') -or
                    $null -eq $firstHit.SelectSingleNode('ProjectTitle')) {
                    Write-Output ($label + ': POSITIVE_TOTAL_BUT_PROJECT_FIELDS_UNRECOGNIZED')
                }
                else {
                    Write-Output ($label + ': VERIFIED_PROJECT_HITS_' + $total)
                    Write-Output 'RESULT: real official project record(s) were returned.'
                    $verified = $true
                }
            }
            elseif ([long]$total -eq 0) {
                Write-Output ($label + ': VALID_XML_BUT_ZERO_HITS_WITH_EXAMPLE_PARAMETERS')
                # The manual's request table (pp.6-8) uses SRWR/displayCnt
                # while its REST example (p.11) uses query/displayCount.
                # Check the other officially documented profile once, on
                # this same endpoint; do not claim zero projects until then.
                $specUri = New-NtisRequestUri -Endpoint $endpoint -Query '나노' -Key $key -Profile Specification
                $specCode = $null
                $specContent = $null
                try {
                    $specResponse = Invoke-WebRequest -Uri $specUri -UseBasicParsing -Method Get -TimeoutSec 20 -MaximumRedirection 0 -ErrorAction Stop
                    $specCode = [int]$specResponse.StatusCode
                    $specContent = [string]$specResponse.Content
                }
                catch {
                    # Never emit raw exception text or URLs containing the key.
                    if ($null -ne $_.Exception.Response) {
                        try { $specCode = [int]$_.Exception.Response.StatusCode } catch { $specCode = $null }
                    }
                    if ($null -eq $specCode) {
                        Write-Output ($label + ': SPECIFICATION_PARAMETERS_NETWORK_OR_OTHER_ERROR')
                    }
                }
                finally {
                    $specUri = $null
                }
                if ($null -ne $specCode -and $specCode -ne 200) {
                    Write-Output ($label + ': SPECIFICATION_PARAMETERS_HTTP_' + $specCode)
                }
                elseif ($specCode -eq 200) {
                    if (!$specContent -or $specContent.Length -gt 1500000 -or
                        $specContent -match '(?i)<!DOCTYPE|<!ENTITY') {
                        Write-Output ($label + ': SPECIFICATION_PARAMETERS_INVALID_XML')
                    }
                    else {
                        try {
                            [xml]$specDoc = $specContent
                            if ($specDoc.DocumentElement.LocalName -ne 'RESULT' -or
                                $null -eq $specDoc.DocumentElement.SelectSingleNode('RESULTSET')) {
                                throw 'Unrecognized response'
                            }
                            $specTotal = [string]$specDoc.RESULT.TOTALHITS
                            $specHit = $specDoc.DocumentElement.SelectSingleNode('RESULTSET/HIT')
                            if ($specTotal -notmatch '^\d+$') {
                                throw 'Unrecognized total'
                            }
                            if ([long]$specTotal -gt 0 -and $null -ne $specHit -and
                                $null -ne $specHit.SelectSingleNode('ProjectNumber') -and
                                $null -ne $specHit.SelectSingleNode('ProjectTitle')) {
                                Write-Output ($label + ': SPECIFICATION_PARAMETERS_VERIFIED_PROJECT_HITS_' + $specTotal)
                                Write-Output 'RESULT: real project records were returned with request-table parameters.'
                                $verified = $true
                            }
                            elseif ([long]$specTotal -eq 0) {
                                Write-Output ($label + ': SPECIFICATION_PARAMETERS_VALID_XML_BUT_ZERO_HITS')
                            }
                            else {
                                Write-Output ($label + ': SPECIFICATION_PARAMETERS_INCONSISTENT_PROJECT_RESPONSE')
                            }
                        }
                        catch {
                            Write-Output ($label + ': SPECIFICATION_PARAMETERS_UNRECOGNIZED_XML')
                        }
                    }
                }
            }
            else {
                Write-Output ($label + ': NONZERO_TOTAL_BUT_NO_PROJECT_ROWS')
            }
        }
        catch {
            Write-Output ($label + ': HTTP_200_BUT_UNRECOGNIZED_RESULT')
        }
        break
    }
}
finally {
    $key = $null
    $secureKey = $null
    $content = $null
}
if (!$verified) {
    Write-Output 'RESULT: no project records verified. Valid zero-hit XML is NOT proof that there are no projects; check access and query handling.'
    exit 2
}
exit 0
