// Comentarios del equipo sobre el explorador del corpus.
//
// El sitio está detrás de Cloudflare Access, que solo deja entrar a los mails autorizados y le pasa
// a esta función el mail de quien escribe en un encabezado. Por eso no hay usuarios ni contraseñas:
// el comentario queda firmado con la identidad que Access ya verificó. Sin Access (por ejemplo, en
// una prueba local) el autor queda como "sin identificar".

const SECCIONES = ["General", "Explorador", "Comparación entre bancos", "Ventanillas",
  "Países y sectores", "Algo que me gustaría ver"];
const MAX = 4000;

const json = (cuerpo, estado = 200) =>
  new Response(JSON.stringify(cuerpo), { status: estado, headers: { "content-type": "application/json; charset=utf-8" } });

export async function onRequestGet({ env }) {
  const { results } = await env.DB.prepare(
    "SELECT id, creado, autor, seccion, texto FROM comentarios ORDER BY id DESC LIMIT 500").all();
  return json(results);
}

export async function onRequestPost({ request, env }) {
  let datos;
  try { datos = await request.json(); } catch { return json({ error: "pedido inválido" }, 400); }
  const texto = String(datos.texto || "").trim();
  const seccion = SECCIONES.includes(datos.seccion) ? datos.seccion : "General";
  if (!texto) return json({ error: "el comentario está vacío" }, 400);
  if (texto.length > MAX) return json({ error: `máximo ${MAX} caracteres` }, 400);
  const autor = request.headers.get("cf-access-authenticated-user-email") || "sin identificar";
  await env.DB.prepare("INSERT INTO comentarios (autor, seccion, texto) VALUES (?, ?, ?)")
    .bind(autor, seccion, texto).run();
  return json({ ok: true }, 201);
}
