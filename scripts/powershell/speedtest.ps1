<#
.SYNOPSIS
    NinjaOne Speed Test Monitor Script
.DESCRIPTION
    Checks for Speedtest CLI, installs if missing, and runs a speed test.
    Outputs results for NinjaOne RMM monitoring and alerting.
.PARAMETER ServerId
    Optional. Specify a server ID to test against a specific Speedtest server.
    To get a list of nearby servers, run: speedtest.exe --servers
.EXAMPLE
    .\speedtest-monitor.ps1
    Runs speed test using automatic server selection
.EXAMPLE
    .\speedtest-monitor.ps1 -ServerId 12345
    Runs speed test using server ID 12345
.NOTES
    Author: Alex Arnold
    Company: Digital Technology Group, LLC
    Date: 2025-12-16
#>

# NinjaOne Automation Metadata
# NINJA_OS: WINDOWS
# NINJA_ARCH: X64

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [int]$ServerId
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Define paths
$SpeedtestPath = "$env:ProgramFiles\Speedtest"
$SpeedtestExe = Join-Path $SpeedtestPath "speedtest.exe"
$TempDir = $env:TEMP
$ZipFile = Join-Path $TempDir "speedtest.zip"

# Function to write output in a format suitable for NinjaOne
function Write-MonitorOutput {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    # Use Write-Host to avoid output capture by functions
    Write-Host "[$timestamp] [$Level] $Message"
}

# Function to check if Speedtest CLI is installed
function Test-SpeedtestInstalled {
    Write-MonitorOutput "Checking for Speedtest CLI installation..."
    Write-MonitorOutput "Looking for: $SpeedtestExe"
    
    # Check in Program Files
    if (Test-Path $SpeedtestExe) {
        Write-MonitorOutput "Speedtest CLI found at: $SpeedtestExe"
        return $true
    }
    
    # Check in PATH
    $pathCheck = Get-Command speedtest.exe -ErrorAction SilentlyContinue
    if ($pathCheck) {
        Write-MonitorOutput "Speedtest CLI found in PATH: $($pathCheck.Source)"
        $script:SpeedtestExe = $pathCheck.Source
        return $true
    }
    
    # Check if files exist in the speedtest directory
    if (Test-Path $SpeedtestPath) {
        $files = Get-ChildItem -Path $SpeedtestPath -ErrorAction SilentlyContinue
        if ($files) {
            Write-MonitorOutput "Files found in $SpeedtestPath : $($files.Name -join ', ')" "WARN"
        }
    }
    
    Write-MonitorOutput "Speedtest CLI not found" "WARN"
    return $false
}

# Function to download and install Speedtest CLI
function Install-SpeedtestCLI {
    Write-MonitorOutput "Starting Speedtest CLI installation..."
    
    try {
        # Create installation directory
        if (-not (Test-Path $SpeedtestPath)) {
            New-Item -ItemType Directory -Path $SpeedtestPath -Force | Out-Null
            Write-MonitorOutput "Created directory: $SpeedtestPath"
        }
        
        # Download URL for latest Windows x64 version
        $DownloadUrl = "https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-win64.zip"
        
        Write-MonitorOutput "Downloading Speedtest CLI from: $DownloadUrl"
        
        # Download the zip file
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipFile -UseBasicParsing
        
        Write-MonitorOutput "Download completed. Extracting files..."
        
        # Extract the zip file
        Expand-Archive -Path $ZipFile -DestinationPath $SpeedtestPath -Force
        
        # Clean up zip file
        Remove-Item $ZipFile -Force
        
        Write-MonitorOutput "Installation completed successfully"
        
        # Verify installation
        if (Test-Path $SpeedtestExe) {
            Write-MonitorOutput "Verified: speedtest.exe is present"
            return $true
        } else {
            Write-MonitorOutput "ERROR: speedtest.exe not found after installation" "ERROR"
            return $false
        }
        
    } catch {
        Write-MonitorOutput "ERROR during installation: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

# Function to run speed test
function Invoke-SpeedTest {
    
    Write-MonitorOutput "Running speed test..."
    
    try {
        # Verify speedtest executable exists
        if (-not (Test-Path $SpeedtestExe)) {
            Write-MonitorOutput "ERROR: Speedtest executable not found at: $SpeedtestExe" "ERROR"
            return $null
        }
        
        # Accept license automatically on first run
        $env:SPEEDTEST_EULA_ACCEPTED = "true"
        
        # Build arguments
        $arguments = "--accept-license --accept-gdpr --format=json"
        $ServerId = $env:serverid
        if ($ServerId -gt 0) {
            $arguments += " --server-id=$ServerId"
            Write-MonitorOutput "Testing against specific server ID: $ServerId"
        }
        
        # Run speedtest with JSON output - use Start-Process for better path handling
        Write-MonitorOutput "Executing speedtest from: $SpeedtestExe"
        
        # Run speedtest and capture output to file
        $processInfo = New-Object System.Diagnostics.ProcessStartInfo
        $processInfo.FileName = $SpeedtestExe
        $processInfo.Arguments = $arguments
        $processInfo.RedirectStandardOutput = $true
        $processInfo.RedirectStandardError = $true
        $processInfo.UseShellExecute = $false
        $processInfo.CreateNoWindow = $true
        
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $processInfo
        $process.Start() | Out-Null
        
        # Read output
        $result = $process.StandardOutput.ReadToEnd()
        $errorOutput = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        
        $exitCode = $process.ExitCode
        
        if ($exitCode -ne 0) {
            Write-MonitorOutput "Speed test failed with exit code: $exitCode" "ERROR"
            Write-MonitorOutput "Error output: $errorOutput" "ERROR"
            return $null
        }
        
        # Log first part of output for debugging
        if ($result.Length -gt 0) {
            Write-MonitorOutput "Raw speedtest output received (length: $($result.Length) chars)"
        } else {
            Write-MonitorOutput "ERROR: No output received from speedtest" "ERROR"
            return $null
        }
        
        # Parse JSON result
        Write-MonitorOutput "Parsing JSON response..."
        $speedData = $result | ConvertFrom-Json
        
        # Validate that we got valid data
        if ($null -eq $speedData) {
            Write-MonitorOutput "ERROR: Parsed data is null" "ERROR"
            return $null
        }
        
        if ($null -eq $speedData.download -or $null -eq $speedData.upload) {
            Write-MonitorOutput "ERROR: Invalid speed test data structure" "ERROR"
            Write-MonitorOutput "Data received (first 500 chars): $($result.Substring(0, [Math]::Min(500, $result.Length)))" "ERROR"
            return $null
        }
        
        Write-MonitorOutput "Speed test data parsed successfully"
        return $speedData
        
    } catch {
        Write-MonitorOutput "ERROR running speed test: $($_.Exception.Message)" "ERROR"
        Write-MonitorOutput "Stack trace: $($_.ScriptStackTrace)" "ERROR"
        return $null
    }
}

# Function to format and display results
function Show-SpeedTestResults {
    param($Data)
    
    if ($null -eq $Data) {
        Write-MonitorOutput "No speed test data available" "ERROR"
        return
    }
    
    # Validate data structure
    $hasDownload = $null -ne $Data.download -and $null -ne $Data.download.bandwidth
    $hasUpload = $null -ne $Data.upload -and $null -ne $Data.upload.bandwidth
    $hasPing = $null -ne $Data.ping -and $null -ne $Data.ping.latency
    
    if (-not $hasDownload -or -not $hasUpload) {
        Write-MonitorOutput "ERROR: Incomplete speed test data" "ERROR"
        Write-Output "RAW DATA: $($Data | ConvertTo-Json -Depth 3)"
        return
    }
    
    # Calculate speeds (bandwidth is in bits/second, convert to Mbps)
    $downloadMbps = [math]::Round($Data.download.bandwidth / 125000, 2)
    $uploadMbps = [math]::Round($Data.upload.bandwidth / 125000, 2)
    $pingMs = if ($hasPing) { [math]::Round($Data.ping.latency, 2) } else { 0 }
    $jitterMs = if ($hasPing -and $Data.ping.jitter) { [math]::Round($Data.ping.jitter, 2) } else { 0 }
    
    # Get server and ISP info safely
    $serverName = if ($Data.server.name) { $Data.server.name } else { "Unknown" }
    $serverLocation = if ($Data.server.location) { $Data.server.location } else { "Unknown" }
    $ispName = if ($Data.isp) { $Data.isp } else { "Unknown" }
    $resultUrl = if ($Data.result.url) { $Data.result.url } else { "N/A" }
    
    Write-Output ""
    Write-Output "============================================"
    Write-Output "         SPEED TEST RESULTS"
    Write-Output "============================================"
    Write-Output ""
    Write-Output "Test Date/Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Output "Server: $serverName - $serverLocation"
    Write-Output "ISP: $ispName"
    Write-Output ""
    Write-Output "Download Speed: $downloadMbps Mbps"
    Write-Output "Upload Speed:   $uploadMbps Mbps"
    Write-Output "Ping:           $pingMs ms"
    Write-Output "Jitter:         $jitterMs ms"
    Write-Output ""
    Write-Output "Result URL: $resultUrl"
    Write-Output "============================================"
    Write-Output ""
    
    # Output key metrics for NinjaOne custom fields/monitoring
    Write-Output "METRICS:"
    Write-Output "DOWNLOAD_MBPS=$downloadMbps"
    Write-Output "UPLOAD_MBPS=$uploadMbps"
    Write-Output "PING_MS=$pingMs"
    Write-Output "JITTER_MS=$jitterMs"
    Write-Output "SERVER=$serverName"
    Write-Output "ISP=$ispName"
}

# Main execution
try {
    Write-Output ""
    Write-Output "========================================"
    Write-Output "  NinjaOne Speed Test Monitor"
    Write-Output "========================================"
    Write-Output ""
    
    # Check if Speedtest CLI is installed
    if (-not (Test-SpeedtestInstalled)) {
        # Install if not present
        $installResult = Install-SpeedtestCLI
        
        if (-not $installResult) {
            Write-MonitorOutput "Failed to install Speedtest CLI. Exiting." "ERROR"
            exit 1
        }
    }
    
    # Run the speed test
    $testResults = Invoke-SpeedTest -ServerId $ServerId
    
    # Only display results if we got valid data
    if ($null -ne $testResults) {
        Show-SpeedTestResults -Data $testResults
        Write-MonitorOutput "Speed test completed successfully"
        exit 0
    } else {
        Write-MonitorOutput "Speed test failed - no valid results" "ERROR"
        exit 1
    }
    
} catch {
    Write-MonitorOutput "CRITICAL ERROR: $($_.Exception.Message)" "ERROR"
    Write-Output $_.ScriptStackTrace
    exit 1
}
