# Sitio del explorador

El explorador se publica en Cloudflare Pages, detrás de Cloudflare Access: solo entran los mails
autorizados, con un código que les llega por correo. Los comentarios del equipo se guardan en una
base D1 de Cloudflare y quedan firmados con el mail que Access verificó.

- `functions/api/comentarios.js`: la función que lee y guarda comentarios.
- `schema.sql`: la tabla de comentarios.
- La página la genera `scripts/explorador_corpus.py` en `data/processed/explorador/`.

Para publicar se copia la página como `index.html` junto a `functions/` y se sube con
`npx wrangler pages deploy`, con la base D1 enlazada con el nombre `DB`. Todo es plan gratuito.
