const CACHE_NAME = 'aether-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('push', (e) => {
  let data = {};
  try { data = e.data.json(); } catch { data = { title: 'Aether', body: e.data?.text() || 'New alert' }; }
  e.waitUntil(
    self.registration.showNotification(data.title || 'Aether SMM OS', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/favicon-32.png',
      tag: data.tag || 'aether-alert',
      data: { url: data.url || '/' },
      vibrate: [200, 100, 200]
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
