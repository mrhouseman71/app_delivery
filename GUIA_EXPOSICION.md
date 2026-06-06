# Guía de Exposición — Vocal Intelligence Pipeline

**Integrantes:** Balda Javier · Caracoix Juan · Casas Facundo  
**Tiempo total:** 20–25 minutos · **Audiencia:** docentes + compañeros del curso

---

## Idea central de la exposición

El hilo conductor es **una sola canción** que atraviesa todo el sistema.
Usás S.O.S de Bogdan Shuvalov de principio a fin: la misma canción que generó el CSV, sobre la que corren las anomalías, sobre la que predice el clasificador, y que llega como stream a Kafka.

Esto hace que la exposición sea una historia lineal, no un catálogo de módulos sueltos.

---

## Estructura en 5 actos (20 min)

```
Acto 1  El problema y el dataset          3 min
Acto 2  Análisis frame a frame            4 min   [demo live: dashboard original]
Acto 3  Comparación entre voces          4 min   [demo live: comparador_dashboard.html]
Acto 4  Anomalías en tiempo real         4 min   [demo live: anomaly_dashboard.html]
Acto 5  Kafka + ML: el pipeline completo  5 min   [demo live: kafka_dashboard.html]
```

---

## Acto 1 · El problema y el dataset (3 min)

**Quién habla:** cualquiera de los tres

**Frase de apertura:**
> "Tienen un cantante con un rango de 3.28 octavas — de A2 a C6 —, que pasa por cinco registros distintos en 90 segundos. La pregunta es: ¿qué le pasa técnicamente a esa voz mientras canta, y cómo lo detectamos en tiempo real?"

**Puntos a cubrir:**

Explicar brevemente qué hace `pipeline.py`: toma el audio, lo procesa con pYIN (librosa) y torchcrepe (red neuronal CNN), y genera un CSV de 1801 filas — un frame cada 50ms — con la nota, la frecuencia, la intensidad y el registro de cada instante.

Mostrar en la pantalla las primeras líneas del CSV (`realtime_frames.csv`). Enfatizar los campos: `time_s`, `note`, `hz`, `confidence`, `intensity`, `register`.

Decir el número clave: **1801 frames, 90 segundos, rango A2–C6, 39 semitonos**. Este CSV es la entrada de todo lo que viene.

---

## Acto 2 · Análisis frame a frame (4 min)

**Quién habla:** el que trabajó más en el challenge original

**Demo:** abrir `challenge_streaming/results/dashboard.html` en el navegador

**Puntos a cubrir:**

El dashboard original muestra el pitch a lo largo del tiempo, la distribución de registros y los momentos de alta intensidad. Señalar con el cursor:

- La zona 32–38s donde el pitch sube a A5 (agudo, cerca del pico de intensidad)
- El momento 59.7s donde aparece por primera vez C6 — la nota sobreaguda
- El pico máximo @ 69.35s: C6 a 36.5 RMS

Explicar la escala log del eje de frecuencias: por qué tiene sentido que la distancia entre A2 (109 Hz) y A3 (220 Hz) sea la misma que entre A3 y A4 (440 Hz).

**Frase de cierre del acto:**
> "Este dashboard nos dice qué está cantando. Los tres módulos que siguen nos dicen qué significa eso."

---

## Acto 3 · Comparación entre voces (4 min)

**Quién habla:** rotación

**Demo:** abrir `idea_c/comparador_dashboard.html`

**Lo que van a mostrar:**

Hacer clic en "Tenor Dramático (estilo Bogdan)" y leer los KPIs: 3.25 oct, Hz medio 502, nota modal E4.

Luego hacer clic en "Barítono Lírico" — el Hz medio cae a 213, el registro grave pasa de 10% a 43%.

Hacer clic en "Soprano Lírica" — Hz medio sube a 693, el registro sobreagudo aparece al 13%.

**Lo que hay que explicar verbalmente:**

El comparador generó frames sintéticos para cada perfil usando el mismo motor de síntesis que el pipeline original. Cada perfil tiene una secuencia de notas, parámetros de vibrato y timbre. El resultado es un dataset de 1056 ventanas de 2 segundos por las que pasa el clasificador.

Mostrar el gráfico radar (está en el dashboard): el Tenor Dramático tiene el rango más amplio (eje "Rango"), pero no el Hz medio más alto — la Soprano lo supera.

**Dato que genera impacto:**
> "El barítono pasa el 43% de su tiempo en registro grave. El tenor dramático solo el 10%. Esa diferencia es suficiente para que el Random Forest los clasifique correctamente el 74% de las veces."

---

## Acto 4 · Anomalías en tiempo real (4 min)

**Quién habla:** el que trabajó más en Idea D

**Demo:** abrir `idea_d/anomaly_dashboard.html`

**Lo que van a mostrar:**

En el dashboard hay un timeline del pitch con líneas de colores marcando los eventos. Señalar:

- La línea naranja (CAIDA_INTENS) a los 35s — caída del 88% (pico 30.2 → actual 3.7)
- La línea violeta (AGUDO_EXTREMO) a los 59.7s — primera nota C6 a 1054 Hz
- Las llamas (CLIMAX_VOCAL) acumuladas entre 60 y 70s

**Explicar la lógica de cada regla:**

BREAK_VOZ: salto de más de 5 semitonos entre frames consecutivos. Detecta el cambio de pecho a cabeza.

CLIMAX_VOCAL: 8 frames consecutivos (0.4s) en registro agudo o sobreagudo. Señala el momento de mayor exigencia.

CAIDA_INTENS: la intensidad actual cae más del 50% respecto al pico de la última ventana de 10 frames. Detecta el final de una frase.

**La pregunta que genera debate:**
> "¿Es lo mismo CLIMAX_VOCAL que simplemente 'nota alta'? No. Una nota alta de 0.2 segundos no es un clímax. El sistema exige 0.4s sostenidos — eso es lo que diferencia una nota de paso de un momento de exposición técnica."

**Número clave:** 212 eventos en 90 segundos. La zona 59–70s concentra la mayor densidad porque ahí está el doble C6.

---

## Acto 5 · Kafka + ML: el pipeline completo (5 min)

**Quién habla:** el que trabajó más en Ideas A y B

**Demo:** abrir `idea_b/kafka_dashboard.html`

**Lo que van a mostrar:**

El dashboard arranca solo y empieza a simular el stream. Dejar que corra en "Tempo real" unos 20 segundos para que se vea el efecto de las ventanas llegando.

Señalar en la pantalla:
- El contador de tópicos (vocal.frames / vocal.analyzed / vocal.alerts) actualizándose
- La barra de confianza — en la zona media de la canción está cerca del 100% para Tenor dramático
- Las alertas apareciendo en el log en tiempo real

**Lo que hay que explicar:**

El producer emite un frame cada 50ms — exactamente la cadencia del análisis pYIN. El consumer acumula 40 frames (2 segundos) y cada 10 frames nuevos (0.5s de audio) clasifica la ventana.

La clasificación llama al Random Forest de la Idea A con 20 features extraídas de esa ventana: Hz medio, mediana, percentiles, variación de intensidad, distribución de registros.

El detector de anomalías (Idea D) corre en paralelo frame a frame y emite al tópico `vocal.alerts` cada vez que detecta un evento nuevo.

**La frase que explica la integración:**
> "El CSV de la base del challenge es la fuente. Los perfiles del comparador son las etiquetas de entrenamiento. El clasificador es el modelo. El detector de anomalías es el filtro de eventos. Kafka es el transporte. Todo corre sobre el mismo dato — el mismo frame de 50ms."

**Cambiar a modo Turbo** (hacer clic en el botón) para mostrar que en demo se puede acelerar sin perder nada del procesamiento.

---

## Cierre (1 min)

**Frase de cierre:**
> "Empezamos con un CSV de 1801 filas y terminamos con un sistema que, ante cualquier audio nuevo, puede decirte el tipo de voz, señalarte los momentos técnicamente relevantes, compararlo con seis perfiles de referencia, y hacerlo todo en streaming a medida que el audio avanza."

Mostrar brevemente el diagrama de arquitectura del README con las 4 capas apiladas.

---

## Reparto sugerido de voces

| Acto | Quién |
|------|-------|
| 1 — El problema | Cualquiera (el que presenta mejor verbalmente) |
| 2 — Dashboard original | El que hizo el challenge |
| 3 — Comparador | El que hizo Idea C |
| 4 — Anomalías | El que hizo Idea D |
| 5 — Kafka + ML | El que hizo Ideas A y B |
| Preguntas | Rotación, cada uno defiende su módulo |

---

## Preguntas probables y respuestas

**¿Por qué Kafka y no simplemente leer el CSV directo?**  
El CSV es batch — procesa todo el audio de una vez y devuelve resultados al final. Kafka convierte eso en streaming: cada frame llega en el momento en que ocurre en el audio. Esto habilita análisis en vivo durante una grabación o un concierto, cosa que el pipeline batch no puede hacer.

**¿El 69% de accuracy en el clasificador es bueno o malo?**  
Depende del contexto. El baseline aleatorio es 16.7% (6 clases). El modelo lo lleva al 69%, o sea 4 veces mejor que el azar. Para 6 clases muy parecidas entre sí (Contratenor y Soprano comparten zona de Hz), y con un dataset sintético de 1233 ventanas, es un resultado sólido. En las dos clases más separadas (Soprano y Barítono) el F1 supera el 80%.

**¿Por qué la feature más importante es int_mean y no hz_mean?**  
Porque la intensidad media es el nivel de proyección vocal — y cada tipo vocal tiene una proyección característica independiente de en qué nota esté. Un barítono operístico y un tenor pop pueden estar en la misma nota (E4, por ejemplo), pero el barítono tiene un nivel de proyección distinto. El hz_mean captura el registro, pero int_mean captura el estilo de emisión.

**¿Qué pasa si el audio tiene ruido o instrumentos?**  
El pipeline base usa Demucs (htdemucs, estado del arte 2024) para separar la voz de los instrumentos antes del análisis pYIN. En el modo demo se usa audio sintético puro, por lo que la separación no es necesaria. Para audio real con banda, activar Demucs con `--no-demucs=False`.

**¿Se podría hacer esto en tiempo real con un micrófono?**  
Sí, con una modificación al producer: en lugar de leer el CSV, capturar audio del micrófono en bloques de 50ms, aplicar pYIN en tiempo real, y emitir cada frame a Kafka. El consumer y el dashboard no cambian. Es un paso natural de extensión del sistema.

---

## Lista de verificación antes de la exposición

- [ ] Abrir los 4 dashboards HTML en pestañas del navegador antes de entrar
- [ ] Verificar que `kafka_dashboard.html` carga correctamente (tiene datos embebidos, no necesita Kafka corriendo)
- [ ] Tener el CSV `realtime_frames.csv` listo para mostrar las primeras líneas
- [ ] Tener el README del repo abierto para mostrar la estructura de carpetas
- [ ] Ensayar las transiciones entre actos — el ritmo importa tanto como el contenido
- [ ] Preparar el diagrama de arquitectura para el cierre (está en el README)

---

## Material de apoyo en el repo

Todos los recursos están en el repositorio. Para la exposición, los cuatro archivos más importantes son:

1. `idea_b/kafka_dashboard.html` — la demo más impactante visualmente
2. `idea_c/comparador_dashboard.html` — para el acto de comparación
3. `idea_d/anomaly_dashboard.html` — para el acto de anomalías
4. `challenge_streaming/results/dashboard.html` — la base de todo
