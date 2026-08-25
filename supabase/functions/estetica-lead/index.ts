import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// estetica-lead — captacion de leads de la demo WhiteMoon · Selene Estetica
// (chatbot "ANA": servicio → subservicio → zona → dia → hora → nombre y telefono).
//
// Inserta el lead en leads_web (sector='estetica', origen='demo-estetica') con la
// service role y avisa por TELEGRAM. Sustituye a estetica-notify (CallMeBot): ni
// apikeys ni claves de Supabase viven ya en el cliente.
//
// Secrets usados (nunca en cliente):
//   - TELEGRAM_BOT_TOKEN        : token del bot de Telegram (obligatorio para avisar)
//   - TELEGRAM_CHAT_ID          : chat destino; si falta se usa CHAT_ID_FALLBACK
//   - SUPABASE_URL              : inyectado por la plataforma
//   - SUPABASE_SERVICE_ROLE_KEY : inyectado por la plataforma
//
// El cliente llama con fetch(keepalive) y, si falla, reintenta con
// navigator.sendBeacon → Blob 'text/plain' (peticion simple, sin preflight).
// Por eso el body se lee como texto y se parsea a mano: llega igual en ambos casos.
//
// Regla del proyecto: si el aviso falla → console.warn, nunca rompe la captura.
//
// Desplegar con:
//   supabase functions deploy estetica-lead --no-verify-jwt --project-ref mlaqtniujnvfxcvcourm

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') ?? '';
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';

// El chat_id no es un secreto (solo identifica el destino); el token si lo es.
const CHAT_ID_FALLBACK = '861432965';

const REST_HEADERS = {
  'Content-Type': 'application/json',
  'apikey': SERVICE_KEY,
  'Authorization': `Bearer ${SERVICE_KEY}`,
};

// Devuelve true solo si Telegram acepto el mensaje, para poder verificar el
// aviso de punta a punta desde la respuesta de la funcion.
async function notificar(text: string): Promise<boolean> {
  const token = Deno.env.get('TELEGRAM_BOT_TOKEN');
  const chatId = Deno.env.get('TELEGRAM_CHAT_ID') || CHAT_ID_FALLBACK;
  if (!token) {
    console.warn('[estetica-lead] sin TELEGRAM_BOT_TOKEN, mensaje:', text);
    return false;
  }
  try {
    const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({ chat_id: chatId, text }),
    });
    if (!r.ok) {
      console.warn('[estetica-lead] Telegram fallo:', r.status, await r.text());
      return false;
    }
    return true;
  } catch (e) {
    console.warn('[estetica-lead] error enviando Telegram:', e);
    return false;
  }
}

const clean = (v: unknown, max: number) => String(v ?? '').slice(0, max).trim();

Deno.serve(async (req: Request) => {
  const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'content-type' };
  if (req.method === 'OPTIONS') return new Response('ok', { headers: cors });
  const json = (obj: unknown, status = 200) =>
    new Response(JSON.stringify(obj), { status, headers: { ...cors, 'Content-Type': 'application/json; charset=utf-8' } });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  try {
    let payload: Record<string, unknown> = {};
    try {
      payload = JSON.parse(await req.text());
    } catch {
      return json({ error: 'body no valido' }, 400);
    }
    const body = (payload.args ?? payload) as Record<string, unknown>;

    const nombre = clean(body.nombre, 80);
    const telefono = clean(body.telefono, 20);
    const servicio = clean(body.servicio, 60);
    const subservicio = clean(body.subservicio, 80);
    const zona = clean(body.zona, 60);
    const citaDia = clean(body.cita_dia, 20);          // ISO (YYYY-MM-DD)
    const citaLabel = clean(body.cita_label, 60);      // "martes 3 de septiembre"
    const citaHora = clean(body.cita_hora, 10);
    const precio = Number(body.precio) > 0 ? Number(body.precio) : 0;

    if (!nombre || telefono.replace(/\D/g, '').length < 9 || !servicio) {
      return json({ error: 'nombre, telefono (9+ digitos) y servicio son obligatorios' }, 400);
    }

    const interes = subservicio ? `${servicio} — ${subservicio}` : servicio;
    const mensaje =
      `Servicio: ${interes}` +
      (precio > 0 ? ` (${precio} €)` : '') +
      (zona ? ` · Zona: ${zona}` : '') +
      (citaLabel || citaHora ? ` · Cita: ${citaLabel || citaDia}${citaHora ? ' a las ' + citaHora : ''}` : '');

    const ins = await fetch(`${SUPABASE_URL}/rest/v1/leads_web`, {
      method: 'POST',
      headers: { ...REST_HEADERS, 'Prefer': 'return=representation' },
      body: JSON.stringify({
        nombre,
        telefono,
        sector: 'estetica',
        interes,
        mensaje,
        origen: 'demo-estetica',
        cita_dia: citaDia || null,
        cita_hora: citaHora || null,
      }),
    });
    const rows = await ins.json();
    const lead = Array.isArray(rows) ? rows[0] : null;
    if (!lead) {
      console.warn('[estetica-lead] insert fallo:', ins.status, JSON.stringify(rows));
      return json({ error: 'no se pudo registrar el lead' }, 500);
    }

    const msg =
      `💅 NUEVA CITA · Selene Estetica (demo)\n` +
      `Cliente: ${nombre}\n` +
      `Tel: ${telefono}\n` +
      `Servicio: ${interes}${precio > 0 ? ` (${precio} €)` : ''}\n` +
      (zona ? `Zona: ${zona}\n` : '') +
      (citaLabel || citaHora ? `Cita: ${citaLabel || citaDia}${citaHora ? ' a las ' + citaHora : ''}\n` : '') +
      `Origen: demo-estetica`;
    const notified = await notificar(msg);

    return json({ ok: true, lead_id: lead.id, notified });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
