// Ano-DM Chrome Extension Background Service Worker
// Automatically intercepts downloads and routes them to Ano-Download Manager

const ANO_DM_API = "http://127.0.0.1:9653/add_download";

chrome.downloads.onCreated.addListener((downloadItem) => {
  const url = downloadItem.finalUrl || downloadItem.url;

  // Ignore data: and blob: URLs
  if (!url || (!url.startsWith("http://") && !url.startsWith("https://"))) {
    return;
  }

  // Cancel Chrome's native download so Ano-DM handles it
  chrome.downloads.cancel(downloadItem.id, () => {
    chrome.downloads.erase({ id: downloadItem.id });
  });

  // Forward to Ano-DM local listener
  fetch(ANO_DM_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      url: url,
      filename: downloadItem.filename || "",
      referrer: downloadItem.referrer || "",
      mime: downloadItem.mime || ""
    })
  }).catch((err) => {
    console.warn("Could not forward download to Ano-DM daemon. Is Ano-DM running?", err);
  });
});
