(function () {
  const pageText = document.body?.innerText || ''
  const links = Array.from(document.querySelectorAll('a'))
  const suspicious = links.filter((a) => /login|verify|account|update|secure|bank|claim|reward|otp/i.test(a.href || a.innerText))
  if (suspicious.length || /verify|bank|password|urgent|invoice/i.test(pageText)) {
    chrome.runtime.sendMessage({ type: 'scan_text', text: `${pageText}\n${links.map((link) => link.href).join('\n')}` }, (response) => {
      if (response?.label === 'scam' || response?.label === 'suspicious') {
        const banner = document.createElement('div')
        banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:999999;background:#ef4444;color:white;padding:12px 16px;font-family:Inter,Arial,sans-serif;font-size:14px;text-align:center;'
        banner.textContent = 'This page may contain phishing content.'
        document.body.appendChild(banner)
      }
    })
  }
})();
