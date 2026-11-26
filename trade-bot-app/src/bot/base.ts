// İstemcinin temel parçaları: hata sınıfı, sunucu adresi denetimi, tutar biçimi.

export class ApiError extends Error {
  constructor(
    public code: string,
    public uncertain = false,
    public status = 0,
  ) {
    super(uncertain ? "İşlemin sonucu belirsiz. Durumu kontrol edin; yeni işlem göndermeyin." : code);
    this.name = "ApiError";
  }
}

// Yalnızca HTTPS kök adresi kabul edilir; kullanıcı adı, sorgu, yol ya da yerel döngü adresi reddedilir.
export function serverOrigin(value: string): string {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("Geçerli bir https adresi girin.");
  }
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/" ||
    /^(localhost|127\.|0\.|\[::1\])/.test(url.hostname)
  )
    throw new Error("Yalnızca https kök adresi kullanılabilir.");
  return url.origin;
}

// "1234.5" -> "1.234,50" (Türkçe biçim). Sayı değilse "—".
export function money(value: string | undefined | null): string {
  if (value == null) return "—";
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return "—";
  return match[1] + match[2].replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "," + (match[3] || "").padEnd(2, "0").slice(0, 2);
}
