# Generates synthetic smoke-test WAVs with the Windows built-in voices.
# These are NOT the evaluation set - real recordings go to eval/audio/ (Day 6).
Add-Type -AssemblyName System.Speech
$out = Join-Path $PSScriptRoot "..\eval\samples"
New-Item -ItemType Directory -Force $out | Out-Null
$samples = @(
  @("de_01_line_status.wav", "Microsoft Hedda Desktop", "Wie ist der Status von Linie 2?"),
  @("de_02_ticket.wav",      "Microsoft Hedda Desktop", "Erstelle ein Wartungsticket fuer Maschine 7, die Spindel ist ueberhitzt."),
  @("de_03_alarms.wav",      "Microsoft Hedda Desktop", "Welche Alarme sind gerade auf Linie 3 aktiv?"),
  @("en_01_line_status.wav", "Microsoft Zira Desktop",  "What is the status of line 4?"),
  @("en_02_ticket.wav",      "Microsoft David Desktop", "Create a maintenance ticket for machine 7."),
  @("en_03_alarms.wav",      "Microsoft Zira Desktop",  "List all critical alarms from the last hour."),
  @("de_04_manual.wav",      "Microsoft Hedda Desktop", "Was bedeutet der Alarm E 204 und was muss ich tun?"),
  @("en_04_manual.wav",      "Microsoft Zira Desktop",  "What do I have to do before I open a machine?")
)
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($s in $samples) {
  $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $synth.SelectVoice($s[1])
  $synth.SetOutputToWaveFile((Join-Path $out $s[0]), $fmt)
  $synth.Speak($s[2])
  $synth.Dispose()
  Write-Output "$($s[0]): $($s[2])"
}
