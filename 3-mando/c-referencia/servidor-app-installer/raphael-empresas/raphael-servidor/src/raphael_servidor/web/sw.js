// Service worker mínimo: permite instalar el panel en el celular. No guarda datos en caché (siempre van al servidor).
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => self.clients.claim());
self.addEventListener("fetch", () => {});
