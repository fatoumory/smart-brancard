# Image du frontend : construction de la PWA avec Node, puis service par nginx
# (lancée par docker compose, voir docker-compose.yml à la racine)

#  1. Construction (npm run build)
FROM node:22-alpine AS construction
WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que le package-lock.json ne change pas
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# L'application appelle l'API à la même adresse qu'elle, sous /api : nginx la transmet au backend.
# Une variable déjà définie passe avant les fichiers .env de Vite
ENV VITE_API_URL=/api
RUN npm run build

#  2. Service des fichiers construits
FROM nginx:1.27-alpine

# Certificat auto-signé pour le HTTPS : sur un téléphone, la caméra (scan du bracelet) et le NFC
# ne fonctionnent qu'en HTTPS. Le navigateur affiche un avertissement à accepter une fois.
RUN apk add --no-cache openssl \
    && openssl req -x509 -nodes -newkey rsa:2048 -days 825 -subj "/CN=smart-brancard" \
       -keyout /etc/nginx/cle.pem -out /etc/nginx/certificat.pem

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=construction /app/dist /usr/share/nginx/html

EXPOSE 80 443
