import "jsr:@supabase/functions-js/edge-runtime.d.ts";

// estetica-notify — notifica por WhatsApp un nuevo lead de la demo Selene · Estetica.
// El lead ya se inserta en leads_web desde el cliente (origen='demo-estetica');
// esta funcion SOLO envia la notificacion WhatsApp via CallMeBot, manteniendo la
// apikey EXCLUSIVAMENTE server-side. Mismo patron que chefka-notify / alejandr-notify.
//
// Secrets del proyecto (Supabase → Edge Functions → Secrets):
//   CALLMEBOT_APIKEY  — apikey de CallMeBot vinculada al numero de WhiteMoon
//   WA_NUMBER         — numero destino del aviso (por defecto 34643199580)
//
// verify_jwt: false (se llama desde el navegador sin sesion; no expone secretos).
//
// Recibe (POST JSON): { nombre, telefono, servicio, subservicio, zona, mensaje }

const DEFAULT_WA = "34643199580";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  let payload: Record<string, unknown> = {};
  try {
    payload = await req.json();
  } catch {
    payload = {};
  }

  const data = (payload.args ?? payload) as Record<string, unknown>;
  const nombre = String(data.nombre ?? "").trim() || "-";
  const telefono = String(data.telefono ?? "").trim() || "-";
  const servicio = String(data.servicio ?? "").trim() || "-";
  const subservicio = String(data.subservicio ?? "").trim() || "-";
  const zona = String(data.zona ?? "").trim() || "-";
  const extra = String(data.mensaje ?? "").trim();

  const message =
    `Nuevo lead Selene Estetica (demo)\n` +
    `Nombre: ${nombre} | Tel: ${telefono}\n` +
    `Servicio: ${servicio} | ${subservicio}\n` +
    `Zona: ${zona}` +
    (extra ? `\n${extra}` : "");

  const notifyPhone = (Deno.env.get("WA_NUMBER") ?? DEFAULT_WA).trim();

  let notified = false;
  try {
    const callmebotKey = Deno.env.get("CALLMEBOT_APIKEY");
    if (callmebotKey) {
      const notifyUrl =
        `https://api.callmebot.com/whatsapp.php?phone=${encodeURIComponent(notifyPhone)}` +
        `&text=${encodeURIComponent(message)}&apikey=${encodeURIComponent(callmebotKey)}`;
      const r = await fetch(notifyUrl);
      notified = r.ok;
      if (!r.ok) {
        console.warn("[estetica-notify] CallMeBot fallo:", r.status);
      }
    } else {
      console.warn("[estetica-notify] sin CALLMEBOT_APIKEY, mensaje:", message);
    }
  } catch (e) {
    console.warn("[estetica-notify] error enviando WhatsApp:", e);
  }

  return json({ ok: true, notified });
});
