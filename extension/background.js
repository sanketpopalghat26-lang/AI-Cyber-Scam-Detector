chrome.runtime.onInstalled.addListener(() => {
  console.log('AI Scam Detector extension installed')
})

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'scan_text') {
    fetch('http://localhost:8000/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: request.text, source: 'extension' }),
    })
      .then((response) => response.json())
      .then((payload) => sendResponse(payload))
      .catch(() => sendResponse({ label: 'suspicious', confidence: 0.7, explanation: { reason: 'Unable to connect to the local detector.' } }))
    return true
  }
  return false
})
