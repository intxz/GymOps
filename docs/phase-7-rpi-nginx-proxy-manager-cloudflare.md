# Fase 7: Raspberry + Nginx Proxy Manager + SSL + Cloudflare

Este documento adapta GymOps a Raspberry Pi (Ubuntu ARM64) usando Nginx Proxy Manager (NPM) como reverse proxy TLS.

Objetivos de seguridad:

- Exponer solo HTTP/HTTPS del reverse proxy (`80/443`).
- Mantener `gym-api`, `grafana` y `prometheus` sin puertos públicos directos.
- No tocar ni publicar Minecraft desde esta configuración.
- Mantener SSH sin exposición pública (acceso por VPN/LAN).

## 1. Variables de entorno

```bash
cp infra/docker/.env.example infra/docker/.env
```

Ajusta al menos:

- `TELEGRAM_BOT_TOKEN`
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`
- `PUBLIC_DOMAIN=a2technology.net`
- `PUBLIC_API_SUBDOMAIN=gymops`
- `PUBLIC_GRAFANA_SUBDOMAIN=grafana-gymops`
- `HERMES_HOME_HOST=/home/raspi/.hermes` (o tu ruta real)
- `NPM_ADMIN_BIND=127.0.0.1:81` (recomendado)

## 2. Levantar stack en Raspberry

```bash
docker compose -f infra/docker/docker-compose.rpi.yml up -d --build
```

Servicios esperados:

- `gym-api` (interno)
- `gym-telegram-bot` (interno)
- `gym-prometheus` (interno)
- `gym-grafana` (interno)
- `gym-npm` (entrada pública 80/443)

## 3. Cloudflare DNS (a2technology.net)

Crear registros `A` apuntando a la IP pública de tu router:

- `gymops.a2technology.net`
- `grafana-gymops.a2technology.net`

Configura cada registro en estado **Proxied** (nube naranja).

Notas:

- No crear subdominio público para panel admin de NPM.
- No tocar registros/puertos de Minecraft.

## 4. Router / NAT

Redirige exclusivamente:

- `80 -> <IP_RASPBERRY>:80`
- `443 -> <IP_RASPBERRY>:443`

No redirigir:

- `22` (SSH)
- `81` (panel NPM)
- `3000` (Grafana)
- `9090` (Prometheus)
- `8000` (API)
- `25565` (Minecraft, salvo tu política actual independiente)

## 5. Configuración inicial NPM

Accede desde LAN o VPN:

- `http://<IP_RASPBERRY>:81`

Crear usuarios admin en NPM y después:

1. `Hosts -> Proxy Hosts -> Add Proxy Host`
2. Host API:
- Domain: `gymops.a2technology.net`
- Scheme: `http`
- Forward Hostname/IP: `gym-api`
- Forward Port: `8000`
3. Host Grafana:
- Domain: `grafana-gymops.a2technology.net`
- Scheme: `http`
- Forward Hostname/IP: `gym-grafana`
- Forward Port: `3000`

## 6. SSL en NPM (Let's Encrypt)

En cada Proxy Host:

1. Pestaña `SSL` -> `Request a new SSL Certificate`
2. Activar:
- `Force SSL`
- `HTTP/2 Support`
- `HSTS Enabled` (opcional al inicio, recomendado luego)
3. Guardar y esperar emisión.

## 7. Cloudflare SSL/TLS

En Cloudflare para `a2technology.net`:

- `SSL/TLS mode = Full (strict)` (recomendado)
- Evitar `Flexible` para no crear bucles de redirección.

Opcional avanzado:

- Activar `Always Use HTTPS` en Cloudflare.
- Evaluar `Authenticated Origin Pulls (AOP)` para endurecer origen.

## 8. Protección de servicios privados

Para servicios sensibles (ej. Grafana):

- En NPM, crear `Access Lists` con Basic Auth.
- Limitar por IP (rango LAN/VPN) cuando sea posible.
- Si quieres cero exposición pública, usar solo VPN y no crear DNS público para ese host.

## 9. Verificación rápida

```bash
docker compose -f infra/docker/docker-compose.rpi.yml ps
curl -I https://gymops.a2technology.net
curl -I https://grafana-gymops.a2technology.net
```

En local (Raspberry), confirmar conectividad interna:

```bash
docker exec gym-npm getent hosts gym-api
docker exec gym-npm getent hosts gym-grafana
```

## 10. Referencias

- Blog base compartido: https://blog.runesoft.net/ssl-y-proxy-inverso-con-nginx-proxy-manager/
- NPM setup oficial: https://develop.nginxproxymanager.com/setup/
- Cloudflare Full (strict): https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/
- Cloudflare Proxy status (DNS proxied): https://developers.cloudflare.com/dns/manage-dns-records/reference/proxied-dns-records/
- Cloudflare Origin CA: https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/
