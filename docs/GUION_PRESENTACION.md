# Guion de Presentación — Vocal Intelligence Pipeline

**Integrantes:** Balda Javier · Caracoix Juan · Casas Facundo  
**Tiempo total:** 20 minutos · **Audiencia:** docentes + compañeros del curso

---

> **Cómo leer este guion**  
> Las frases entre comillas `"…"` son las palabras exactas a decir.  
> Los bloques `[ACCIÓN]` indican qué hacer en pantalla.  
> Los tiempos entre paréntesis `(3 min)` son orientativos.

---

## Parte 1 — Introducción, dataset y arquitectura *(6 min)*

---

### 1.1 · Apertura y planteamiento del problema *(1 min)*

**Quién habla:** el presentador más suelto del grupo

`[ACCIÓN]` Pantalla en negro o con el título del proyecto. Nada más.

---

"Imaginen que tienen la grabación de un cantante. Escuchan la canción — suena bien. Pero la pregunta que nos hacemos nosotros es otra: ¿qué está haciendo técnicamente esa voz mientras canta? ¿Cuándo está al límite de su registro? ¿Cuándo cae la intensidad de golpe? ¿A qué tipo de voz se parece?

Eso es lo que construimos. Un sistema que toma cualquier audio vocal y produce, en tiempo real, tres cosas: una clasificación del tipo de voz, alertas sobre los eventos técnicos vocales mientras ocurren, y una comparación contra seis perfiles de referencia.

Todo esto corriendo sobre Apache Kafka. El audio entra como un stream de frames y sale como análisis en vivo."

---

### 1.2 · El dataset — la canción que atraviesa todo *(1.5 min)*

**Quién habla:** el mismo

`[ACCIÓN]` Abrir `realtime_frames.csv` en el editor o en una terminal. Mostrar las primeras 8 filas.

---

"El punto de partida es esta canción: S.O.S de Bogdan Shuvalov. 90 segundos de audio.

El pipeline original — `pipeline.py` — toma ese audio, lo procesa con dos algoritmos de detección de pitch: pYIN de librosa, que es el algoritmo clásico, y torchcrepe, una red neuronal convolucional entrenada para estimar frecuencia fundamental.

El resultado es este CSV. Cada fila es un frame de 50 milisegundos. Tienen siete columnas: el tiempo, la nota, la frecuencia en Hz, la confianza de la detección, la intensidad RMS, el registro vocal, y un booleano que indica si hay voz en ese frame.

Los números que importan: **1801 frames totales, 1747 con voz detectada — el 97% de la canción es cantada**. El rango va de A2, que son 109 Hz, hasta C6, que son 1059 Hz. **39.3 semitonos, 3.28 octavas**. La nota más frecuente es G5 y el registro dominante es medio-agudo.

Este CSV es la entrada de todo lo que viene después."

---

### 1.3 · Arquitectura general *(2 min)*

**Quién habla:** el mismo o rotar

`[ACCIÓN]` Mostrar el diagrama de arquitectura del README. Si no hay proyector, leerlo en voz alta mientras señalás el README abierto en el navegador.

---

"El sistema se organiza en cuatro capas que construimos de forma incremental.

La capa base es el pipeline de análisis — el challenge original. Genera el CSV de frames.

Sobre ese CSV construimos tres módulos en paralelo:

El comparador multi-artista, que es la Idea C: tomamos el pipeline de síntesis de audio del challenge y lo extendimos para generar seis perfiles vocales distintos — barítono, soprano, tenor pop, contratenor, mezzo y el propio Bogdan. Para cada uno extraemos 16 métricas que van desde el rango en octavas hasta la densidad melódica. Ese dataset de seis perfiles es lo que después alimenta el clasificador.

El detector de anomalías, Idea D: definimos seis tipos de eventos vocales con reglas deterministas — saltos bruscos de pitch, sostenimiento de notas agudas, caídas de intensidad, silencios estructurales. Cada regla tiene parámetros ajustados sobre los datos reales de la canción.

El clasificador ML, Idea A: un Random Forest entrenado sobre ventanas deslizantes de dos segundos. 20 features por ventana, 1056 muestras, 69% de accuracy en seis clases. La feature más importante es la intensidad media — no el pitch, sino el nivel de proyección de la voz.

Y encima de todo esto, la Idea B: Kafka. El producer lee el CSV y emite un mensaje por frame, respetando el timing de 50 ms. El consumer acumula frames en un buffer deslizante, clasifica cada ventana y detecta anomalías. Los resultados van a dos tópicos distintos: `vocal.analyzed` y `vocal.alerts`.

La integración clave es esta: el mismo frame de 50ms que generó el CSV es la unidad de todo el sistema. El producer lo emite, el consumer lo clasifica, el detector lo analiza. No hay transformaciones intermedias."

---

### 1.4 · Dashboard original — el análisis frame a frame *(1.5 min)*

**Quién habla:** el que trabajó en el challenge

`[ACCIÓN]` Abrir `challenge_streaming/results/dashboard.html` en el navegador.

---

"Este es el punto de partida visual — el dashboard original del challenge. Muestra tres cosas.

Arriba, el timeline de pitch: la frecuencia en hertz a lo largo del tiempo, en escala logarítmica. La escala log es importante porque el oído humano percibe el pitch de forma logarítmica — la distancia entre A2 y A3 suena igual que la distancia entre A3 y A4, aunque en Hz la segunda diferencia sea el doble de grande.

`[ACCIÓN]` Señalar con el cursor la zona 32-38 segundos, luego el pico a los 59-70 segundos.

Esta zona entre los 32 y 38 segundos es donde el pitch sube hacia A5 — primer pico de intensidad. Y acá, entre los 59 y 70 segundos, está el momento más exigente técnicamente: la primera aparición de C6 a los 59.7 segundos, y el pico de intensidad absoluto a los 69.35 segundos — C6 a 36.5 RMS.

A la derecha, la distribución de registros: 33% en medio-agudo, 29% en agudo, 23% en medio-grave. Solo el 10% en grave, pero hay notas que bajan hasta A2.

Este dashboard nos dice *qué* está cantando. Los tres módulos que vienen a continuación nos dicen *qué significa* eso."

---

---

## Parte 2 — Comparador multi-artista *(4 min)*

---

**Quién habla:** el que trabajó en la Idea C

`[ACCIÓN]` Abrir `comparador_dashboard.html`. Las seis tarjetas de artistas deben verse en pantalla.

---

"El comparador responde una pregunta concreta: ¿en qué se diferencia técnicamente la voz de Bogdan de otros tipos vocales? Para responderla, construimos seis perfiles de referencia usando el mismo motor de síntesis del pipeline original.

Veamos el sistema completo.

`[ACCIÓN]` Señalar la grilla de seis tarjetas en la parte superior del dashboard.

Cada tarjeta representa un perfil. El rango que aparece debajo del nombre es el eje de partida: de A2 a C6 para el tenor dramático, de F2 a A4 para el barítono, de C4 a F6 para la soprano.

**Los KPIs del artista seleccionado**

`[ACCIÓN]` Hacer clic en la tarjeta del Tenor Dramático (Bogdan). Leer los KPIs en voz alta.

Cuando seleccionamos a Bogdan, los KPIs nos dan el resumen cuantitativo: **3.25 octavas de rango**, Hz medio de **501.8** — o sea, el centro de su voz está alrededor de B4 —, nota modal E4, **22 notas distintas** en la secuencia, y densidad melódica de 0.44 cambios por segundo.

`[ACCIÓN]` Hacer clic en la tarjeta del Barítono.

Cambiamos al barítono. El rango baja a 2.33 octavas. El Hz medio cae a **212.8** — casi la mitad. La nota modal es G2, que está dos octavas por debajo de la E4 de Bogdan. Y la densidad melódica baja a 0.34 — el barítono canta más lento, con notas más sostenidas.

**Distribución de registros — la huella vocal de cada perfil**

`[ACCIÓN]` Señalar el gráfico de barras horizontales "Distribución de registros (%)".

Este es el gráfico más revelador. Muestra cuánto tiempo pasa cada voz en cada registro.

`[ACCIÓN]` Volver al Barítono y señalar la barra de registro grave.

El barítono pasa el **43.3% del tiempo en registro grave y 42.2% en medio-grave**. Prácticamente no tiene presencia en registros agudos. Ratio agudo/grave: cero.

`[ACCIÓN]` Hacer clic en Soprano.

La soprano es el opuesto exacto: cero por ciento en registro grave, 40.6% en medio-agudo, 32.2% en agudo, y **13.3% en sobreagudo** — el único perfil que tiene presencia sobreaguda regular. Su Hz medio es 692.7. Ratio agudo/grave: 3.28 — por cada segundo en registro grave, pasa 3.28 segundos en registros agudos.

`[ACCIÓN]` Volver a Bogdan.

Bogdan está en el medio: 10% grave, 35% medio-agudo, 28.3% agudo. Es el perfil más amplio.

**Timeline de pitch**

`[ACCIÓN]` Señalar el gráfico "Timeline de pitch (notas × tiempo)".

Este gráfico muestra la secuencia de notas a lo largo del tiempo, coloreadas por registro. Acá se ve visualmente el arco dramático de cada perfil: el tenor dramático empieza grave, sube progresivamente, alcanza el C6 en la zona central, y baja al final. El barítono se mantiene en la zona baja durante toda la secuencia.

**Gráficos comparativos globales**

`[ACCIÓN]` Señalar los tres gráficos de barras pequeños: Rango vocal, Frecuencia media, Densidad melódica.

Estos tres gráficos muestran todos los perfiles a la vez. En rango vocal, el tenor dramático lidera con 3.25 octavas — más del doble que el barítono. En frecuencia media, la soprano supera al contratenor: 692 Hz contra 550. En densidad melódica, Bogdan es el más activo con 0.44 cambios por segundo.

**El radar — seis dimensiones en un vistazo**

`[ACCIÓN]` Señalar el gráfico radar.

El radar normaliza seis métricas distintas en una escala de 0 a 100 para poder compararlas visualmente. Los ejes son: rango, Hz medio, densidad melódica, porcentaje de tiempo en registros agudos, intensidad media y número de notas distintas.

Lo que inmediatamente se ve: la soprano tiene la forma más elongada hacia el eje de Hz y de agudos. El barítono tiene la forma más compacta. El tenor dramático tiene el radio más grande en rango — eso refleja sus 3.25 octavas.

**Stacked bar — el registro como identidad de la voz**

`[ACCIÓN]` Señalar el gráfico de barras apiladas.

Este gráfico consolida todo: cada barra es un artista, cada color es un registro. La distribución de colores es la identidad acústica de ese tipo de voz. Cuanta más distancia visual entre dos barras, más fácil le resulta al clasificador distinguirlos.

Esa diferencia es exactamente lo que el Random Forest aprende — lo vemos en el siguiente módulo."

---

---

## Parte 3 — Detección de anomalías *(4 min)*

---

**Quién habla:** el que trabajó en la Idea D

`[ACCIÓN]` Abrir `anomaly_dashboard.html`.

---

"El comparador nos dice cómo es la voz en términos estadísticos. El detector de anomalías nos dice qué eventos técnicamente significativos ocurren mientras se canta.

Detectamos **212 eventos en 90 segundos**, organizados en seis tipos.

**Los KPIs — el resumen del análisis**

`[ACCIÓN]` Señalar la fila de KPIs superior.

Seis métricas resumen el análisis completo. Total de eventos: 212. Severidad alta: 4 eventos. Clímax vocales: 95 — casi uno por segundo en la zona más exigente. Inestabilidades: 64. Caídas de intensidad: 51. Y el agudo extremo: 1 — la primera vez que el cantante llega a C6 sobreagudo.

**Los seis tipos de anomalía — qué detecta cada regla**

Antes de mirar los gráficos, explico qué detecta cada tipo.

BREAK_VOZ detecta un salto de más de 5 semitonos entre frames consecutivos. Es la firma del cambio de registro de pecho a cabeza, o de una ornamentación brusca. No es simplemente una nota aguda — es el salto en sí.

CLIMAX_VOCAL detecta 8 frames consecutivos — 0.4 segundos — en registro agudo o sobreagudo. La diferencia con una nota alta de pasaje es la duración. Una nota de 0.2 segundos no es un clímax. El sistema exige sostén.

CAIDA_INTENS detecta una caída de intensidad de al menos el 50% en una ventana de 10 frames respecto al pico local. Señala el final de una frase, un corte, o un cambio dinámico brusco de forte a piano.

AGUDO_EXTREMO es un evento único: la primera nota en registro sobreagudo de toda la canción. Solo dispara una vez.

SILENCIO_LARGO detecta más de 15 frames consecutivos sin voz — 0.75 segundos. Identifica las pausas estructurales de la canción.

INESTABILIDAD mide el coeficiente de variación del Hz en una ventana de 8 frames. Si supera el 2.5%, hay variación excesiva — puede ser un vibrato demasiado amplio, una transición entre notas, o desafinación.

**El timeline de pitch con eventos superpuestos**

`[ACCIÓN]` Señalar el gráfico superior "Pitch (Hz) con eventos anotados".

Este es el gráfico central. El azul es el pitch real de la canción. Las líneas verticales son los eventos detectados, cada color corresponde a un tipo.

`[ACCIÓN]` Señalar las líneas a los 30s, 35s, 44s, 59.7s, y la concentración de eventos entre 60-70s.

A los **30 segundos**, el primer clímax: F5 sostenida 0.6 segundos. La primera vez que la voz se asienta en registro agudo.

A los **35 segundos**, una línea azul intensa — la primera caída severa de intensidad: **caída del 88%**, de un pico de 30.2 a 3.7 RMS. Eso es el final de la primera sección fuerte de la canción.

A los **44 segundos**, el silencio estructural: 0.8 segundos sin voz. La pausa entre las dos secciones principales.

A los **59.7 segundos**, el evento más importante de toda la canción: **AGUDO_EXTREMO** — primera aparición de C6 a **1054 Hz**. Único, irrepetible. El momento en que la voz supera el límite del registro agudo por primera vez.

Entre los **60 y los 70 segundos** está la mayor densidad de eventos: múltiples CLIMAX_VOCAL, incluyendo el sostenimiento de C6 a los 67.4 segundos. Y a los 70 segundos, la segunda caída severa — el **81% de caída** post-clímax, cuando la sección de mayor exigencia termina.

A los **90 segundos**, la caída final: **93%**. El cierre de la canción.

**Timeline de intensidad**

`[ACCIÓN]` Señalar el gráfico de intensidad RMS.

Este segundo gráfico muestra la dinámica a lo largo del tiempo. Las líneas rojas verticales marcan las caídas de intensidad detectadas. Se puede ver claramente el crescendo hacia el clímax en la zona 55-70 segundos, y las tres caídas severas que particionan la canción en secciones.

**Eventos por tipo y severidad**

`[ACCIÓN]` Señalar los dos gráficos inferiores izquierdos.

El gráfico de barras horizontales confirma la distribución: 95 clímax vocales, 64 inestabilidades, 51 caídas de intensidad. Los clímax son el evento más frecuente porque la canción pasa mucho tiempo en registro agudo.

La torta de severidad muestra que el **61% de los eventos son de severidad media, 37% baja, y solo 4 eventos son de severidad alta**. Los cuatro eventos de alta severidad son los que ya vimos: la caída del 88%, el agudo extremo C6, la caída del 81% post-clímax, y la caída final del 93%.

**El log de eventos clave**

`[ACCIÓN]` Señalar la tabla inferior de eventos.

Esta tabla es el output que va al tópico `vocal.alerts` en Kafka. Cada fila tiene el tiempo, el tipo, la severidad y la descripción del evento. Esto es lo que recibe cualquier sistema downstream — puede ser un dashboard, un sistema de alerta, o un almacén de datos para análisis posterior."

---

---

## Parte 4 — Pipeline Kafka en streaming *(5 min)*

---

**Quién habla:** el que trabajó en las Ideas A y B

`[ACCIÓN]` Abrir `kafka_dashboard.html`. El stream empieza automáticamente en modo lento.

---

"Hasta ahora todo lo que vimos fue batch: tomamos el CSV, procesamos todo, vemos los resultados. El pipeline Kafka transforma exactamente el mismo análisis en streaming: los frames llegan en tiempo real y el sistema responde a medida que llegan.

**Arquitectura de tópicos — cómo fluye la información**

`[ACCIÓN]` Señalar las tres pastillas de tópicos en la parte superior del dashboard.

El sistema usa tres tópicos Kafka.

`vocal.frames` es la entrada: cada mensaje es un frame de 50ms con la nota, la frecuencia, la intensidad y el registro. El producer lee el CSV y emite un mensaje por fila, con un sleep de 50ms entre cada uno para respetar el timing real del audio. En modo turbo, sin sleep, emite todo a máxima velocidad.

`vocal.analyzed` es la salida del clasificador: cada mensaje tiene la ventana procesada, la predicción, la confianza, y el vector completo de probabilidades para las seis clases. Se emite cada 10 frames nuevos — cada 0.5 segundos de audio.

`vocal.alerts` es la salida del detector de anomalías: cada mensaje es un evento con tipo, severidad y tiempo de ocurrencia. Se emite en el instante en que se detecta.

`[ACCIÓN]` Señalar los contadores debajo de las pastillas actualizándose.

Los contadores debajo de cada pastilla muestran cuántos mensajes circularon por cada tópico desde el inicio del stream.

**Los KPIs en vivo — el estado del pipeline**

`[ACCIÓN]` Señalar la fila de cinco KPIs.

Cinco métricas muestran el estado del pipeline en tiempo real.

Ventanas procesadas: cuántas ventanas de 2 segundos el consumer ya clasificó.

Frames recibidos: estimación de mensajes en `vocal.frames`. Como el consumer procesa ventanas de 40 frames con stride de 10, podemos estimar el total.

Confianza media: promedio de confianza del clasificador en las últimas 10 ventanas. Lo que vamos a ver es que varía entre 65% y 98% dependiendo de la zona de la canción.

Alertas emitidas: conteo acumulado de mensajes a `vocal.alerts`.

FPS efectivos: ventanas clasificadas por segundo — mide el throughput real del pipeline.

**El clasificador en acción — por qué varía la confianza**

`[ACCIÓN]` Señalar el gráfico de confianza por ventana en el lado izquierdo.

Este gráfico muestra la confianza del clasificador para cada ventana a lo largo del tiempo. Lo importante es que no es plano — varía.

El dataset de esta demo tiene tres artistas en secuencia: Bogdan primero, luego el barítono, luego la soprano. El modelo predice "Tenor dramático" para todos — lo cual es esperable porque fue entrenado principalmente con ese perfil.

Pero la confianza baja: cuando el stream llega a los frames del barítono, la confianza cae al **65-70%** porque el barítono tiene Hz bajo y registro grave, lo que activa parcialmente esa clase. La confianza del barítono llega al 20% en esas ventanas. El modelo duda, aunque igual predice Tenor dramático.

Esto es exactamente el comportamiento correcto: el clasificador no es binario, trabaja con probabilidades. Esa distribución de probabilidades es lo que permite detectar ambigüedad.

`[ACCIÓN]` Señalar el gráfico de torta "Distribución de predicciones".

En esta demo con datos multi-artista, el 100% de las 254 ventanas se predicen como Tenor dramático — porque ese fue el perfil dominante en el entrenamiento. Lo que diferencia a los artistas no es la predicción final sino la distribución de probabilidades en `probas{}`.

**El log de alertas — vocal.alerts en vivo**

`[ACCIÓN]` Señalar la sección inferior "Stream de alertas — vocal.alerts".

Las alertas aparecen en tiempo real a medida que el stream avanza. Cada fila que aparece es un mensaje que en un sistema real estaría llegando al consumer como un evento Kafka independiente, con su timestamp, su tipo y su severidad.

Los 24 eventos de esta demo son todos INESTABILIDAD — aparecen porque los frames sintéticos de los perfiles tienen variación de pitch en las transiciones entre notas.

**Modo turbo — para la demo**

`[ACCIÓN]` Hacer clic en el botón "⚡ Turbo".

En modo turbo el producer no respeta los 50ms entre frames — emite todo lo más rápido posible. Esto hace que las 254 ventanas se procesen en segundos en lugar de minutos. Para una demo en vivo es la opción práctica; para un análisis real se usa el modo tempo real para que el timing del análisis corresponda al timing del audio.

`[ACCIÓN]` Hacer clic en "↺ Reiniciar" para demostrar que el stream se puede repetir.

Y el stream es repetible: reiniciando el consumer desde el offset inicial del tópico, el análisis empieza de cero. Esto es una ventaja directa de Kafka respecto a un pipeline batch: el dato persiste en el log del broker y se puede reprocesar cuantas veces sea necesario."

---

---

## Parte 5 — Cierre *(1 min)*

---

**Quién habla:** el que abrió la presentación

`[ACCIÓN]` Volver al diagrama de arquitectura del README.

---

"Para cerrar, volvemos al punto de partida.

Empezamos con un CSV de 1801 filas — el análisis pYIN de 90 segundos de audio.

Con ese CSV construimos cuatro módulos que se integran verticalmente: el comparador da las etiquetas de entrenamiento al clasificador, el clasificador da las predicciones al consumer de Kafka, el detector de anomalías da las alertas al segundo tópico, y Kafka transporta todo en tiempo real.

El resultado es un sistema que, ante cualquier audio vocal nuevo, puede decirte el tipo de voz con un 69% de precisión en seis clases, señalarte los 212 momentos técnicamente relevantes, compararlo contra seis perfiles de referencia en 16 métricas, y hacerlo todo frame a frame a medida que el audio avanza.

Muchas gracias."

---

---

## Preguntas probables — respuestas preparadas

**¿Por qué Kafka y no simplemente leer el CSV directamente?**

"El CSV es batch: procesas todo y devolvés resultados al final. Kafka convierte el mismo análisis en streaming: cada frame llega en el momento en que ocurre en el audio. Esto habilita casos que el batch no puede cubrir — análisis en vivo durante una grabación, alertas en tiempo real para un coach vocal, o múltiples consumers en paralelo: uno clasifica, otro guarda en base de datos, otro actualiza un dashboard."

**¿El 69% de accuracy es un buen resultado?**

"El baseline aleatorio es 16.7% para seis clases. El modelo lo lleva al 69%, cuatro veces mejor que el azar. Para seis clases vocales con zonas de Hz superpuestas — el contratenor y la soprano comparten la región 500-700 Hz — y con un dataset sintético de 1233 ventanas, es un resultado sólido. Las dos clases más separadas, Soprano y Barítono, tienen F1 por encima del 80%."

**¿Por qué la feature más importante es int_mean y no hz_mean?**

"Porque la intensidad media captura el nivel de proyección vocal, que es característico de cada tipo independientemente de la nota que esté cantando. Un barítono operístico y un tenor pop pueden estar en la misma nota — E4, por ejemplo — pero el barítono tiene un nivel de proyección diferente. El hz_mean captura el registro, pero int_mean captura el estilo de emisión."

**¿Qué pasa con audio que tiene instrumentos?**

"El pipeline usa Demucs — el modelo htdemucs, estado del arte de 2024 — para separar la voz del resto antes del análisis pYIN. En modo demo usamos audio sintético puro, así que la separación no es necesaria. Para audio real con banda, Demucs corre antes del análisis."

**¿Se podría hacer en tiempo real con micrófono?**

"Sí. La modificación es solo en el producer: en lugar de leer el CSV, capturás audio del micrófono en bloques de 50ms, aplicás pYIN, y emitís cada frame a Kafka. El consumer, el clasificador y el detector de anomalías no cambian nada. Es la extensión natural del sistema."

---

---

## Checklist final — antes de entrar a la sala

- [ ] Dashboard original abierto en pestaña 1
- [ ] `comparador_dashboard.html` abierto en pestaña 2
- [ ] `anomaly_dashboard.html` abierto en pestaña 3
- [ ] `kafka_dashboard.html` abierto en pestaña 4
- [ ] `realtime_frames.csv` abierto en editor o terminal
- [ ] README abierto con el diagrama de arquitectura visible
- [ ] Cronómetro preparado para medir los 20 minutos
- [ ] Ensayar al menos una vez las transiciones entre partes
