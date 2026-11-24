import { spawn } from "node:child_process";

const script = `
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$mode = $env:TRADE_AI_GPT_DPAPI_MODE
$inputText = [Console]::In.ReadToEnd()
if ($mode -eq 'encrypt') {
  $plain = [Text.Encoding]::UTF8.GetBytes($inputText)
  $protected = [Security.Cryptography.ProtectedData]::Protect($plain, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
  [Console]::Out.Write([Convert]::ToBase64String($protected))
} elseif ($mode -eq 'decrypt') {
  $protected = [Convert]::FromBase64String($inputText.Trim())
  $plain = [Security.Cryptography.ProtectedData]::Unprotect($protected, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
  [Console]::Out.Write([Text.Encoding]::UTF8.GetString($plain))
} else { throw 'Unknown DPAPI operation.' }
`;

function invoke(mode, input) {
  return new Promise((resolve, reject) => {
    const child = spawn("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", script], {
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
      env: { ...process.env, TRADE_AI_GPT_DPAPI_MODE: mode },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (data) => { stdout += data; });
    child.stderr.on("data", (data) => { stderr += data; });
    child.once("error", reject);
    child.once("close", (code) => code === 0 ? resolve(stdout) : reject(new Error(`Windows DPAPI failed (${code}): ${stderr.trim()}`)));
    child.stdin.end(input, "utf8");
  });
}

export const windowsDpapiEncryption = {
  id: "windows-dpapi-current-user-v1",
  isAvailable: () => process.platform === "win32",
  async encrypt(plaintext) { return Buffer.from((await invoke("encrypt", plaintext)).trim(), "base64"); },
  async decrypt(ciphertext) { return invoke("decrypt", Buffer.from(ciphertext).toString("base64")); },
};
