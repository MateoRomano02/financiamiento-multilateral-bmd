-- Comentarios del equipo sobre el explorador. Base D1 de Cloudflare, plan gratuito.
CREATE TABLE IF NOT EXISTS comentarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  creado TEXT NOT NULL DEFAULT (datetime('now')),
  autor TEXT NOT NULL,
  seccion TEXT NOT NULL,
  texto TEXT NOT NULL
);
