# Tam ESLint denetimi

Başlangıç: 4 hata, 0 uyarı (`.artifacts/rc-baseline-lint.log`). Son: `npm run lint` PASS, 0 hata (`.artifacts/rc-lint-final.log`). Hiçbir kural kapatılmadı.

| Dosya | Düzeltme | Davranış/kabul |
|---|---|---|
| AnalysisNewsRisk.tsx | useState(Date.now) | Saat mount anında başlar; interval aynen korunur |
| CalendarPanel.tsx | useState(Date.now) | Takvim/countdown mantığı korunur |
| MarketChart.tsx | useState(Date.now) | Tek satır; grafik/veri akışı korunur |
| RiskCalculator.tsx | Koşullu render state reset + effect cleanup | Sembol veya marketFresh değişince loading/result/error temizlenir; taslak korunur; eski istek abort edilir |

Risk regresyon testi SELL senaryosunda mock sonucu gösterir, sembol değişiminde sonucu kaldırır, sermaye/fiyat/yön taslağını korur. Test ilk taslağında SELL stop fiyatı yanlış taraftaydı; uygulama doğru biçimde reddetti, fixture düzeltildi.

Promotion testleri `.artifacts` altında tam hedef kopyaları üretir. İlk yeniden lint bu kopyaları ve onların config köklerini tarayıp 208 parsing/lint hatası verdi. Üretilen `.artifacts/**` ve `release/**` global ignore kapsamına alındı, parserOptions.tsconfigRootDir import.meta.dirname ile sabitlendi. Bu, gerçek src dosyalarını veya testleri gizlemez. `eslint .` bütün gerçek projeyi denetler. eslint.config.js QA yapılandırmasıdır; runtime payload içinde değildir.

Orijinal kaynaklarda bu düzeltmeler yapılmadı. Önceki teslim belgelerindeki 4 hata bilgisi o tarihteki durumdur; RC için bu belge geçerlidir.
