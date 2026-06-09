# Guion de Presentación — Vocal Intelligence Pipeline
## (Versión actualizada — Dashboard Unificado)

**Integrantes:** Balda Javier · Caracoix Juan · Casas Facundo  
**Tiempo total:** 22 minutos · **Audiencia:** docentes + compañeros del curso

---

> **Cómo leer este guion**  
> Las frases entre comillas `"…"` son las palabras exactas a decir.  
> Los bloques `[ACCIÓN]` indican qué hacer en pantalla.  
> Los bloques `[SCRIPT]` explican el código que generó lo que están mostrando.  
> Los tiempos entre paréntesis son orientativos.

> **Setup antes de entrar a la sala**  
> Abrir `vocal_unified_dashboard.html` en el navegador. Es el único archivo que necesitás. Tiene los cuatro módulos en pestañas. Cargar el audio de la canción antes de empezar (botón 🎵 en la pestaña "Análisis base").

---

## Parte 1 — Introducción, dataset y arquitectura *(6 min)*

---

### 1.1 · Apertura *(1 min)*

**Quién habla:** el presentador más suelto del grupo

`[ACCIÓN]` Pantalla con el título del proyecto. El dashboard puede estar visible de fondo pero sin interactuar aún.

---

"Para este trabajo, decidimos ampliar nuestro analisis de audio vocal. Nuestro resultado es un sistema que toma cualquier audio vocal y produce, en tiempo real, tres cosas: una clasificación del tipo de voz, alertas sobre los eventos técnicos vocales mientras ocurren, y una comparación contra seis perfiles de referencia.

Todo esto corriendo sobre Apache Kafka."

---

### 1.2 · El dataset y el script base *(2 min)*

**Quién habla:** el mismo

`[ACCIÓN]` Abrir `realtime_frames.csv` y `pipeline.py` en el editor o terminal. Mostrar las primeras 8 filas.

---

"El punto de partida es esta canción: S.O.S de Bogdan Shuvalov. 90 segundos de audio.

El script que genera estos datos es `pipeline.py` — el challenge original. Tiene cuatro funciones principales."

`[SCRIPT — pipeline.py]`

> **Explicar brevemente:**
>
> `generate_synthetic_audio()` — genera el audio de demo con síntesis ADSR, vibrato y armónicos. Para audio real, se usa `--audio` o `--youtube` con `audio_loader.py`.
>
> `separate_vocals_demucs()` — antes del análisis, Demucs separa la voz de los instrumentos. Usa el modelo `htdemucs`, que es el estado del arte a 2024 en separación de fuentes.
>
> `analyze_audio()` — el núcleo. Procesa el audio frame a frame: `FRAME_LENGTH = 2048` samples, `HOP_LENGTH = 512`, lo que da un frame cada 23ms a 22050 Hz. Aplica pYIN de librosa para pitch y torchcrepe para refinar con una CNN. Produce la lista de frames.
>
> `compute_metrics()` — toma la lista de frames y calcula todo lo que van a ver en el dashboard: nota modal, rango, distribución de registros, momentos destacados.

"El resultado es este CSV. Cada fila es un frame de 50 milisegundos. Siete columnas: tiempo, nota, Hz, confianza de detección, intensidad RMS, registro vocal, y si hay voz activa.

**1801 frames, 1747 con voz detectada — el 97% de la canción. Rango A2–C6, 39 semitonos, 3.28 octavas. Este CSV es la entrada de todo lo que viene después.**"

---

### 1.3 · Arquitectura general *(1.5 min)*

**Quién habla:** el mismo o rotar

`[ACCIÓN]` Mostrar el diagrama de arquitectura del README.

---

"El sistema tiene cuatro capas construidas de forma incremental.

La base es el pipeline de análisis — el challenge. Genera el CSV.

Sobre ese CSV construimos tres módulos en paralelo: el comparador multi-artista con `artist_profiles.py` y `vocal_comparador.py`, el detector de anomalías con `anomaly_detector.py`, y el clasificador ML con `vocal_classifier.py`.

Y encima de todo esto, Kafka: `vocal_producer.py` emite el CSV como stream, `vocal_consumer.py` aplica el clasificador y el detector en tiempo real y manda los resultados a dos tópicos distintos.

La integración clave: el mismo frame de 50ms es la unidad de todo el sistema. Es lo que produce el pipeline, lo que emite el producer, lo que procesa el consumer, y lo que ven en el dashboard."

---

### 1.4 · Dashboard base — análisis frame a frame *(1.5 min)*

**Quién habla:** el que trabajó en el challenge

`[ACCIÓN]` Dashboard unificado, **pestaña "📊 Análisis base"**. Dar play al audio (si está cargado).

---

"Esta primera pestaña muestra el análisis original del challenge. Noten que la nota en el centro de la barra del player se actualiza en tiempo real con el audio — está sincronizada con los 583 frames del CSV.

Los cinco KPIs en la parte superior son el resumen estático de la canción: 3.28 octavas de rango, nota modal G5, Hz promedio 502.5, pico de 36.5 RMS, 97% de frames con voz.

`[ACCIÓN]` Señalar el gráfico de pitch superior izquierdo.

El pitch está en escala logarítmica — igual a cómo lo percibe el oído. La distancia entre A2 y A3 es visualmente la misma que entre A3 y A4. Se ven claramente el ascenso progresivo hasta la zona de los 60–70 segundos.

`[ACCIÓN]` Señalar la zona 59–70s en el gráfico, luego el gráfico de intensidad.

Acá, entre los 59 y 70 segundos, está el momento más exigente: la primera nota sobreaguda C6 a los 59.7s, y el pico de intensidad absoluto a los 69.35 segundos — 36.5 RMS.

Este panel nos dice qué está cantando. Los tres que siguen nos dicen qué significa eso."

---

---

## Parte 2 — Comparador multi-artista *(4 min)*

---

**Quién habla:** el que trabajó en la Idea C

`[ACCIÓN]` Dashboard, **pestaña "🎙 Comparador"**.

---

### Los scripts que generan este panel

`[SCRIPT — artist_profiles.py]`

> **Explicar:**
>
> Define seis perfiles vocales como diccionarios Python, cada uno con:
> - `sequence`: lista de tuplas `(nota, t_inicio, t_fin, intensidad)` — la partitura del perfil
> - `timbre`: parámetros de síntesis — tasa de vibrato (4.8–6.8 Hz según tipo), profundidad de vibrato, pesos de los armónicos
>
> Usa el mismo motor de `generate_demo.py` del challenge: síntesis aditiva con envolvente ADSR y vibrato. El barítono tiene vibrato más lento (4.8 Hz) y más armónicos. El contratenor tiene vibrato rápido (6.8 Hz) y armónicos suaves, característico del falsete.

`[SCRIPT — vocal_comparador.py]`

> **Explicar:**
>
> `extract_metrics_from_sequence(profile)` — convierte la secuencia de notas a frames sintéticos a 20 fps y calcula las 16 métricas: rango en octavas y semitonos, Hz medio ponderado por duración, nota modal, distribución de registros en porcentaje, métricas de dinámica e intensidad, densidad melódica y ratio agudo/grave.
>
> `load_from_csv(csv_path, tipo_vocal)` — permite agregar artistas reales desde el CSV del pipeline. Es así como el análisis de Bogdan entra al comparador: sus 1801 frames se procesan con la misma función que los perfiles sintéticos.
>
> `build_dataset()` + `save_dataset()` — construye el JSON y el CSV que alimentan el clasificador y el dashboard.

---

"El comparador responde una pregunta concreta: ¿en qué se diferencia técnicamente la voz de Bogdan de otros tipos vocales?

Para responderla, generamos seis perfiles sintéticos con `artist_profiles.py`. Cada perfil tiene una secuencia de notas, parámetros de vibrato y timbre. Luego `vocal_comparador.py` extrae 16 métricas de cada perfil."

`[ACCIÓN]` Hacer clic en la tarjeta "Tenor Dramático (estilo Bogdan)". Leer los KPIs.

"El tenor dramático tiene **3.25 octavas de rango**, Hz medio **501.8**, nota modal E4, 22 notas distintas.

`[ACCIÓN]` Hacer clic en "Barítono Lírico".

El barítono: 2.33 octavas, Hz medio **212.8** — la mitad. Nota modal G2.

`[ACCIÓN]` Señalar el gráfico de distribución de registros.

Acá está la diferencia más clara. El barítono pasa el **43.3% del tiempo en registro grave**. El tenor dramático, solo el 10%. La soprano: cero por ciento en grave, 32.2% en agudo y 13.3% en sobreagudo.

`[ACCIÓN]` Señalar el gráfico de timeline de pitch.

El timeline muestra la secuencia de notas coloreadas por registro. El arco dramático de Bogdan — grave al principio, ascenso al sobreagudo, descenso al final — es inmediatamente visible.

`[ACCIÓN]` Señalar los tres gráficos comparativos: Rango, Hz medio, Densidad.

Estos tres gráficos ponen a todos los artistas juntos. En rango, Bogdan lidera. En Hz medio, la soprano supera al contratenor. En densidad melódica, Bogdan es el más activo: 0.44 cambios por segundo.

`[ACCIÓN]` Señalar el radar.

El radar normaliza seis métricas en 0–100. La soprano tiene la forma más elongada hacia Hz y agudos. El barítono, la más compacta. El tensor dramático tiene el radio más grande en rango.

`[ACCIÓN]` Señalar el stacked bar.

Cada barra es la identidad acústica de un tipo de voz. Cuanta más distancia visual entre dos barras, más fácil le resulta al clasificador distinguirlos. Esta distribución es exactamente lo que el Random Forest aprende."

---

---

## Parte 3 — Detección de anomalías *(4 min)*

---

**Quién habla:** el que trabajó en la Idea D

`[ACCIÓN]` Dashboard, **pestaña "⚡ Anomalías"**.

---

### El script que genera este panel

`[SCRIPT — anomaly_detector.py]`

> **Explicar los parámetros clave:**
>
> El módulo define seis constantes configurables al principio del archivo:
>
> `SEMITONE_JUMP_THRESH = 5` — semitonos mínimos para BREAK_VOZ. Con 5 semitonos ya es un salto de tercera mayor — claramente intencional.
>
> `CLIMAX_MIN_FRAMES = 8` — frames consecutivos en agudo para CLIMAX_VOCAL. 8 × 50ms = 0.4 segundos. Por debajo de eso es una nota de paso, no un clímax.
>
> `INTENSITY_DROP_THRESH = 0.50` — caída del 50% del pico local en la ventana de `INTENSITY_WINDOW = 10` frames.
>
> `SILENCE_MIN_FRAMES = 15` — 15 × 50ms = 0.75 segundos de silencio para SILENCIO_LARGO.
>
> `INSTABILITY_CV_THRESH = 0.025` — coeficiente de variación del 2.5% en la ventana de 8 frames.
>
> `COOLDOWN_FRAMES = 5` — entre dos eventos del mismo tipo tiene que haber al menos 5 frames de separación. Evita que el mismo evento dispare múltiples veces.
>
> La clase `VocalAnomalyDetector` procesa los frames en un loop con una ventana deslizante (`deque`). Seis métodos privados, uno por tipo de anomalía. El método `detect()` los llama en orden sobre cada frame y retorna la lista de eventos ordenados por tiempo.
>
> Se puede correr standalone:
> ```
> python anomaly_detector.py --csv results/realtime_frames.csv --out anomalies.json
> ```
> O integrarlo al pipeline con `pipeline_with_anomaly.py`, que importa el módulo original sin modificarlo y agrega la detección al final.

---

"El comparador nos dice cómo es la voz estadísticamente. El detector nos dice qué eventos técnicamente significativos ocurren mientras se canta.

Detectamos **212 eventos en 90 segundos**, con seis tipos definidos por reglas sobre los frames.

`[ACCIÓN]` Señalar los seis KPIs superiores.

212 eventos totales, 4 de severidad alta, 95 clímax vocales, 64 inestabilidades, 51 caídas de intensidad, 1 agudo extremo.

`[ACCIÓN]` Señalar el gráfico de pitch con eventos anotados.

Las líneas verticales sobre el pitch son los eventos. El color identifica el tipo — naranja para CLIMAX_VOCAL, rojo para CAIDA_INTENS, violeta para AGUDO_EXTREMO.

A los **30 segundos**: primer clímax, F5 sostenida 0.6s.

A los **35 segundos**: caída del **88%** de intensidad — de un pico de 30.2 a 3.7 RMS. El final de la primera sección fuerte.

A los **44 segundos**: silencio estructural de 0.8 segundos. La pausa entre secciones.

A los **59.7 segundos**: AGUDO_EXTREMO — primera aparición de C6 a 1054 Hz. Evento único, irrepetible, detectado por `_detect_agudo_extremo()` con una bandera booleana que se activa una sola vez.

Entre **60 y 70 segundos**: la mayor densidad de clímax. C6 sostenida a los 67.4s. Luego la caída del 81% post-clímax a los 70s. Y la caída final del 93% al cerrar la canción.

`[ACCIÓN]` Señalar el gráfico de barras de tipos y la torta de severidad.

De los 212 eventos, el 61% son de severidad media, el 37% baja, y solo 4 son de alta severidad. Esos cuatro son los que ya vimos: las tres caídas severas y el agudo extremo.

`[ACCIÓN]` Señalar el log de eventos.

Este log es el output del tópico `vocal.alerts` en Kafka. Cada fila es un mensaje con tiempo, tipo, severidad y descripción."

---

---

## Parte 4 — Pipeline Kafka en streaming *(5 min)*

---

**Quién habla:** el que trabajó en Ideas A y B

`[ACCIÓN]` Dashboard, **pestaña "🔀 Kafka Stream"**. No presionar ▶ todavía.

---

### Los scripts que generan este panel

`[SCRIPT — vocal_producer.py]`

> **Explicar:**
>
> Conecta al broker con `confluent-kafka.Producer` y con reintentos automáticos (`conectar_producer()`). Crea el tópico `vocal.frames` si no existe.
>
> La función `producir()` itera sobre los frames y para cada uno llama a `producer.produce(topic, key=artist_id, value=json_frame)`. La clave es el `artist_id` — permite que Kafka particione por artista si se escala.
>
> El parámetro crítico es `fast=False` por defecto: entre frames hay un `time.sleep(0.05)` — exactamente 50ms — para respetar el timing del audio original. Con `--fast` ese sleep desaparece y el stream va a la máxima velocidad del broker.
>
> También puede generar frames sintéticos desde los perfiles de `artist_profiles.py` sin necesitar el CSV: `python vocal_producer.py --demo --artist soprano`.

`[SCRIPT — vocal_consumer.py]`

> **Explicar:**
>
> Lee del tópico `vocal.frames` con `confluent-kafka.Consumer` en un grupo de consumer `vocal-analyzer-v1`.
>
> Mantiene dos estructuras de estado:
> - `frame_buffer = deque(maxlen=40)` — los últimos 40 frames. 40 × 50ms = 2 segundos de audio.
> - `all_frames = []` — todos los frames desde el inicio, para el detector de anomalías.
>
> Cada vez que acumula 10 frames nuevos (`STRIDE_FRAMES = 10`), llama a `procesar_ventana_clasificador()`: extrae las 20 features, corre el Random Forest, y produce un mensaje a `vocal.analyzed` con la predicción, la confianza y el vector completo de probabilidades.
>
> En paralelo, `procesar_anomalias()` corre cada 20 frames sobre todos los frames acumulados. Compara contra los eventos ya emitidos con un set de deduplicación por `(time, tipo)`. Los eventos nuevos van a `vocal.alerts`.
>
> En el notebook se ejecutan producer y consumer en paralelo con `threading.Thread`.

`[SCRIPT — vocal_classifier.py]` (referencia rápida)

> El Random Forest se entrena sobre ventanas de 2 segundos. `WINDOW_SEC = 2.0`, `STRIDE_SEC = 0.5`. 20 features por ventana extraídas por `extract_features()`: media, mediana, percentiles y variación de Hz; media, desviación y CV de intensidad; porcentaje en cada registro. El modelo se guarda en `vocal_rf.pkl` y se carga en el consumer con `VocalClassifier.load()`.

---

"Hasta ahora todo lo que vimos fue batch: tomamos el CSV, procesamos todo, vemos los resultados. El pipeline Kafka transforma exactamente el mismo análisis en streaming.

`[ACCIÓN]` Señalar las tres pastillas de tópicos.

El sistema usa tres tópicos. `vocal.frames` es la entrada — un frame por mensaje, 50ms entre mensajes. `vocal.analyzed` es la salida del clasificador — una predicción cada 0.5 segundos de audio. `vocal.alerts` es la salida del detector — un mensaje cada vez que se detecta un evento.

`[ACCIÓN]` Presionar **▶ Tempo real**.

El stream arranca. Dejar que corra unos 15 segundos.

`[ACCIÓN]` Señalar los KPIs actualizándose.

Ventanas procesadas, frames recibidos, confianza media, alertas emitidas, FPS efectivos. Todos se actualizan en tiempo real a medida que el consumer procesa las ventanas.

`[ACCIÓN]` Señalar el panel de probabilidades.

Esto es lo que el consumer emite a `vocal.analyzed` para cada ventana: no solo la predicción final, sino el vector completo de probabilidades para las seis clases. Noten que Tenor Dramático domina al principio — es el perfil del CSV de Bogdan.

`[ACCIÓN]` Esperar a que aparezca alguna alerta en el log. Señalarla.

Cada alerta que aparece en el log sería un mensaje que en un sistema real llega al consumer como un evento Kafka independiente, con su timestamp y su tipo.

`[ACCIÓN]` Hacer clic en **⚡ Turbo**.

En modo turbo el producer no respeta los 50ms — emite todo lo más rápido posible. Las 254 ventanas se procesan en segundos. Para una demo en vivo es la opción práctica.

`[ACCIÓN]` Hacer clic en **↺ Reiniciar** para mostrar el replay.

Y el stream es repetible: el dato persiste en el log del broker y se puede reprocesar. Eso es una ventaja directa de Kafka respecto a un pipeline batch."

---

---

## Parte 5 — Cierre *(1 min)*

---

**Quién habla:** el que abrió la presentación

`[ACCIÓN]` Volver al diagrama de arquitectura del README. O mostrar el dashboard con las cuatro pestañas visibles.

---

"Para cerrar: empezamos con un CSV de 1801 filas — el análisis pYIN de 90 segundos de audio.

Con ese CSV construimos cuatro módulos que se integran verticalmente: `artist_profiles.py` y `vocal_comparador.py` dan las etiquetas de entrenamiento a `vocal_classifier.py`. `anomaly_detector.py` detecta los 212 eventos sobre los mismos frames. Y `vocal_producer.py` con `vocal_consumer.py` conectan todo sobre Kafka.

El resultado: un sistema que, ante cualquier audio vocal nuevo, puede decirte el tipo de voz, señalarte los momentos técnicamente relevantes, compararlo contra seis perfiles de referencia, y hacerlo todo frame a frame a medida que el audio avanza.

Muchas gracias."

---

---

## Preguntas probables — respuestas preparadas

**¿Por qué Kafka y no simplemente leer el CSV directamente en el consumer?**

"El CSV es batch: procesás todo y devolvés resultados al final. Kafka convierte el mismo análisis en streaming: cada frame llega en el momento en que ocurre en el audio. El consumer no sabe cuántos frames van a llegar — reacciona a cada mensaje por separado. Eso habilita casos que el batch no puede cubrir: análisis en vivo durante una grabación, múltiples consumers en paralelo — uno clasifica, otro guarda en base de datos —, y replay del stream para debugging sin re-ejecutar el análisis."

**¿Por qué el clasificador usa ventanas de 2 segundos y no frame a frame?**

"Un solo frame de 50ms no tiene suficiente información para clasificar el tipo de voz. El Hz de un frame depende de la nota que se esté cantando en ese instante, no del tipo vocal. La ventana de 2 segundos captura la distribución estadística de pitch e intensidad — mediana, percentiles, CV — que sí es característica del tipo vocal independientemente de qué nota esté cantando. El stride de 0.5s garantiza que las predicciones se actualicen cada medio segundo."

**¿El 69% de accuracy es un buen resultado?**

"El baseline aleatorio es 16.7% para seis clases. El modelo lo lleva al 69%, cuatro veces mejor que el azar. Para seis clases con zonas de Hz superpuestas — contratenor y soprano comparten la región 500–700 Hz — y con un dataset sintético de 1233 ventanas, es sólido. Las clases más separadas, Soprano y Barítono, tienen F1 por encima del 80%."

**¿Por qué la feature más importante es `int_mean` y no `hz_mean`?**

"Porque la intensidad media captura el nivel de proyección vocal, que es característico del tipo independientemente de la nota. Un barítono y un tenor pop pueden estar en la misma nota — E4, por ejemplo — pero el barítono tiene un nivel de proyección diferente. El `hz_mean` captura el registro, pero `int_mean` captura el estilo de emisión."

**¿Se podría hacer en tiempo real con micrófono?**

"Sí, la modificación es solo en el producer: en lugar de leer el CSV, capturás audio del micrófono en bloques de 50ms, aplicás pYIN, y emitís cada frame a Kafka. El consumer, el clasificador y el detector no cambian nada."

**¿Por qué hay dos métodos de detección de pitch — pYIN y torchcrepe?**

"pYIN es el algoritmo clásico de detección de pitch por autocorrelación. Es rápido y funciona bien en voces limpias. torchcrepe es una CNN entrenada sobre millones de frames de audio con anotaciones de pitch — es más robusto con ruido y voces con vibrato fuerte. En el pipeline los dos corren y se compara la confianza: se usa torchcrepe cuando pYIN tiene baja confianza."

---

---

## Checklist final — antes de entrar a la sala

- [ ] `vocal_unified_dashboard.html` abierto en el navegador
- [ ] Audio WAV de la canción cargado (botón 🎵 en pestaña "Análisis base")
- [ ] Verificar que la nota se actualiza al dar play al audio
- [ ] `realtime_frames.csv` abierto en editor para mostrar en la Parte 1.2
- [ ] README abierto con el diagrama de arquitectura visible (para 1.3 y cierre)
- [ ] Cronómetro preparado
- [ ] Ensayar al menos una vez las transiciones entre pestañas del dashboard
- [ ] Preparar la respuesta a "¿por qué el 69% es aceptable?" — es la más probable
