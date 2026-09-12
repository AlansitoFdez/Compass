# Subfase 5.7 — README

## Plan acordado

El README actual está organizado por **cómo se construyó el proyecto**: una lista de fases
con su estado, tablas por fase, y el relato del embudo intercalado con el de la
observabilidad. Eso sirve para auditar, y para eso ya está `docs/phases/`. No sirve para lo
único que este README tiene que conseguir: que alguien que llega de un enlace entienda en
treinta segundos qué es esto y en dos comandos lo tenga corriendo.

Además dice cosas que ya no son verdad. Promete que `OPENROUTER_API_KEY` es obligatoria
(la 5.5 la hizo opcional), manda instalar Node y arrancar `npm run dev` (la 5.5 metió el
dashboard en el compose), y sus números del embudo son de antes de la última corrida.

### Estructura, en el orden en que alguien la necesita

1. **Qué es**, en tres líneas, y **una captura del dashboard**. Hoy no hay ni una imagen en
   todo el repositorio, y es lo que más cambia la primera impresión de quien llega.
2. **Arrancar**: dos comandos, arriba del todo, antes de cualquier explicación.
3. **Cómo funciona**: el recorrido ingesta → embudo → agente → veredicto.
4. **Las decisiones que importan**, con los números reales detrás: por qué el veredicto no
   lo emite el modelo, por qué las citas se verifican en Python, por qué híbrido y no sólo
   vectorial, y cuánto cuesta de verdad un análisis.
5. **Stack** y **qué queda fuera a propósito**.

El relato por subfases no se borra: se queda en `docs/phases/` y se enlaza como «el
razonamiento completo». Un README limpio con cuarenta documentos de decisiones detrás dice
más que un README que intenta ser las dos cosas.

### Las capturas

Con Edge en modo *headless*, que ya está en la máquina: ninguna dependencia nueva, ningún
Playwright. Van a `docs/images/` y se enlazan con ruta relativa, para que GitHub las sirva
sin depender de nada externo.

### Criterios de aceptación

1. Lo primero que se ve es qué es Compass y una captura real del dashboard; el primer
   bloque de comandos es el de arrancar, y son **dos**, sin Node ni `npm install`.
2. Todo número del README está **remedido hoy**, con el comando que lo produce nombrado al
   lado.
3. Las imágenes están versionadas en el repositorio y se ven con ruta relativa.
4. No queda ninguna afirmación que contradiga `.env.example`, `docker-compose.yml` o el
   comportamiento real de la aplicación — la clave opcional incluida.
5. Desaparece la lista de fases con su estado; el relato queda enlazado, no incrustado.
6. Todo enlace interno apunta a un fichero que existe.

## Progreso
