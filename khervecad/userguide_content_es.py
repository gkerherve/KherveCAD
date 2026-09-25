"""The User Guide's chapters, in Spanish.

Mirrors ``userguide_content.py`` chapter for chapter — same anchors,
same structure, same ``figure()``/``kbd()`` calls — with the prose
translated. Loaded by ``userguide.py`` when the active language is
``es`` (``language.current_language()``); kept as its own module
rather than JSON entries because it is a translated document, not a
table of short UI strings.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""


def chapters():
    from .userguide import figure, kbd
    K = kbd
    return [
        ("welcome", "Bienvenida", f"""
<p>KherveCAD es un programa de CAD para quienes quieren sólidos
reales, imprimibles y exportables sin tener que aprender antes un
lenguaje de programación. Usted dibuja, extruye, combina y coloca
piezas; entre bastidores, cada paso se convierte en una línea de un
programa <b>OpenSCAD</b>, y OpenSCAD es el motor que lo transforma en
geometría exacta.</p>
<p>Una sola idea que recordar: <b>su modelo es un árbol de
objetos</b>. Cada herramienta añade una fila a ese árbol o modifica
una. El programa de la pestaña <b>Código</b> se escribe a partir del
árbol, así que ambos siempre coinciden &mdash; puede trabajar con el
que prefiera.</p>
{figure("window", "La ventana de KherveCAD con un modelo de ejemplo "
        "cargado.")}
<table>
<tr><td><b>1</b></td><td><b>Árbol de objetos y pestañas</b> &mdash; el
propio modelo. Principal (el ensamblaje), Objeto (la pieza que se está
construyendo), Colecciones, Variables y Código.</td></tr>
<tr><td><b>2</b></td><td><b>Propiedades</b> &mdash; cada ajuste del
objeto seleccionado: tamaños, posiciones, ángulos, color.</td></tr>
<tr><td><b>3</b></td><td><b>Boceto 2D</b> &mdash; una cuadrícula en
milímetros donde dibujar perfiles y arrastrar piezas a su
lugar.</td></tr>
<tr><td><b>4</b></td><td><b>Vista previa 3D</b> &mdash; el resultado
sólido. Orbite, desplace y haga zoom con el ratón.</td></tr>
<tr><td><b>5</b></td><td><b>Herramientas de dibujo y sólidos</b>
&mdash; herramientas de boceto, medición y formas 3D en un
clic.</td></tr>
<tr><td><b>6</b></td><td><b>Barra de herramientas principal</b>
&mdash; archivo, deshacer, las operaciones (agrupadas), el ajuste
(snap), los controles del boceto y la vista 3D.</td></tr>
</table>
<p><b>La selección es compartida.</b> Haga clic en un objeto en
cualquier lugar &mdash; árbol, 2D o 3D &mdash; y quedará seleccionado
en todos ellos: el panel Propiedades muestra sus ajustes, el boceto lo
delinea y la vista 3D lo tiñe de rojo.</p>
<p><b>Pase el cursor sobre cualquier icono</b> para ver una información
sobre lo que hace y cómo usarlo, paso a paso. Pulse {K("F1")} para
volver a esta guía en cualquier momento.</p>
"""),

        ("first-part", "Su primera pieza en cinco minutos", f"""
<p>Este tutorial crea una placa con un agujero &mdash; los cuatro
movimientos con los que se construyen la mayoría de las piezas:
<i>dibujar, extruir, añadir, cortar</i>.</p>

<h3>Paso 1 &mdash; dibujar un rectángulo</h3>
<ol>
<li>Elija la herramienta <b>Rectángulo</b> en la barra de herramientas
izquierda (o pulse {K("R")}).</li>
<li>En el boceto 2D, pulse en una esquina, arrastre hasta la otra y
suelte. El tamaño se muestra en vivo en milímetros.</li>
<li>Escriba valores exactos en <b>Propiedades</b>: Ancho 60, Alto
40.</li>
</ol>
<p>Como dibujó en la pestaña <b>Principal</b>, KherveCAD convierte la
forma en un nuevo <b>Objeto</b> (una pieza) y abre la pestaña
<b>Objeto</b> sobre él: las piezas se construyen en la pestaña Objeto
y se disponen en Principal.</p>
{figure("tutorial_1_rectangle", "Un rectángulo, dibujado y "
        "dimensionado. La pestaña Objeto se ha abierto sobre la "
        "nueva pieza.")}

<h3>Paso 2 &mdash; extruirlo en una placa</h3>
<ol>
<li>Con el rectángulo seleccionado, abra el grupo <b>Extrusión</b> de
la barra de herramientas principal y elija <b>Extrusión lineal</b>.</li>
<li>En Propiedades, ponga la <b>Altura</b> en 8. El rectángulo ahora
es una placa: en el árbol, <i>Extrusión lineal</i> envuelve a
<i>Rectángulo</i>.</li>
</ol>
{figure("tutorial_2_extrude", "La extrusión lineal envuelve el "
        "rectángulo y le da altura.")}

<h3>Paso 3 &mdash; añadir un cilindro donde irá el agujero</h3>
<ol>
<li>Haga clic en <b>Cilindro</b> en la barra de herramientas
izquierda. Aparece en el origen, dentro de la pieza que está
editando.</li>
<li>En Propiedades ponga ambos radios en 8, Altura en 20 y Z en
&minus;6, para que atraviese la placa por completo.</li>
</ol>
{figure("tutorial_3_cylinder", "El cilindro atraviesa la placa; está "
        "seleccionado, así que aparece teñido y se muestran sus "
        "ajustes.")}

<h3>Paso 4 &mdash; cortar el agujero</h3>
<ol>
<li>En el árbol, haga clic en <i>Extrusión lineal</i> y luego
Ctrl+clic en <i>Cilindro</i> (primero el cuerpo, luego la
herramienta de corte).</li>
<li>Abra el grupo <b>Combinar</b> y elija <b>Diferencia</b>. El
cilindro se resta de la placa.</li>
</ol>
{figure("tutorial_4_difference", "Diferencia: el primer objeto menos "
        "todos los que le siguen. El agujero lo corta el motor "
        "OpenSCAD.")}
<p>Eso es una pieza terminada. Guárdela con {K("Ctrl+S")}, expórtela
para impresión 3D con <b>Archivo &rsaquo; Exportar STL</b>, o haga
clic en <b>A Principal</b> para colocarla en un ensamblaje. Todo lo
que ha hecho se puede deshacer paso a paso con {K("Ctrl+Z")}.</p>
<p class='tip'><i>Consejo:</i> los mismos cuatro movimientos con otras
formas permiten hacer casi cualquier cosa: un polígono extruido en una
escuadra, círculos recortados en una placa para una brida, texto
extruido y recortado para una placa identificativa.</p>
"""),

        ("window", "La ventana, panel por panel", f"""
<h3>Las pestañas sobre el árbol</h3>
<p><b>Principal</b> es el <i>ensamblaje</i>: cada pieza de su
documento, una por fila, colocada donde corresponde. La casilla
<b>Segmentos comunes ($fn)</b> de arriba fija cuán suave es cada
círculo, esfera y cilindro (más alto es más suave y más lento);
desmárquela para que cada forma use su propio valor.</p>
{figure("tab_main", "Pestaña Principal: las piezas del documento y "
        "su colocación.", 430)}
<p><b>Objeto</b> es donde se <i>construye</i> una pieza. Elija la
pieza en el desplegable, o <b>+ Nuevo</b> para empezar una; el botón
de lápiz la renombra y <b>A Principal</b> coloca otra copia de ella en
el ensamblaje. Mientras esta pestaña está abierta, las vistas 2D y 3D
muestran solo esta pieza, con su propio origen.</p>
{figure("tab_object", "Pestaña Objeto: la construcción de una pieza, "
        "paso a paso.", 430)}
<p><b>Variables</b> es una pequeña hoja de cálculo de números con
nombre (<i>w</i>, <i>wall</i>&hellip;) que puede usar en cualquier
campo. <b>Código</b> muestra el programa OpenSCAD y permite
editarlo.</p>
{figure("tab_variables", "Pestaña Variables: valores con nombre "
        "usados por expresiones como <i>w - 2 * wall</i>.", 430)}

<h3>Propiedades</h3>
<p>Cada ajuste del objeto seleccionado, generado según su tipo:
tamaños, posición, ángulos, segmentos, color, texto. Cualquier campo
numérico también acepta una <b>expresión</b> &mdash;
<code>wall * 2</code>, <code>i * 10</code>, <code>cos(a) * r</code>
&mdash; así es como un modelo se vuelve ajustable. Un polígono
muestra sus vértices como una tabla editable.</p>
{figure("properties", "Propiedades de un cilindro.", 430)}

<h3>El boceto 2D</h3>
<p>Una cuadrícula en milímetros sobre un plano del modelo &mdash;
<b>Superior (XY)</b>, <b>Frontal (XZ)</b> o <b>Lateral (YZ)</b>,
elegido en la barra de herramientas principal. Los dos ejes tienen
los colores del gizmo 3D (X rojo, Y verde, Z azul). Las formas se
dibujan aquí; una forma seleccionada muestra su tamaño con flechas de
cota y tiradores cuadrados para redimensionarla. Las piezas 3D
aparecen como contornos rellenos que se pueden arrastrar. El
arrastre con el botón central desplaza la vista, la rueda hace zoom,
y la escala de la esquina inferior izquierda indica cuánto mide un
cuadro de la cuadrícula. La pequeña barra de la esquina superior
derecha hace lo mismo sin ratón: las flechas desplazan, las lupas
hacen zoom (mantener pulsado repite), <b>Enfocar</b> (&#x25CE;)
encuadra la pieza seleccionada esté donde esté &mdash; útil cuando
una pieza está lejos del origen &mdash; y <b>Encajar todo</b> muestra
todo.</p>
{figure("sketch", "El boceto 2D: un rectángulo seleccionado con sus "
        "cotas automáticas, y un círculo.")}

<h3>La vista previa 3D</h3>
<p>El resultado sólido. <b>Arrastrar con el botón izquierdo</b>
orbita, <b>arrastrar con el botón derecho o central</b> desplaza la
vista, la <b>rueda</b> hace zoom y un <b>doble clic</b> encuadra todo
el modelo. La barra flotante de la esquina superior izquierda ajusta
el <b>brillo</b> y el <b>contraste</b> (&#x27F2; los restablece) y
tiene <b>Redibujar</b> (&#x27F3;). La barra de la esquina superior
derecha gira el modelo, desplaza la vista, hace zoom, encuadra la
pieza seleccionada (<b>Enfocar</b>) o el modelo entero (<b>Encajar
todo</b>). La etiqueta de abajo indica qué está viendo: <i>vista
previa integrada</i> (instantánea, aproximada) u <i>OpenSCAD</i>
(exacta), y cuántas piezas ya son exactas.</p>
{figure("view3d_plate", "La vista previa 3D con la barra de "
        "iluminación.")}

<h3>La barra de estado</h3>
<p>De izquierda a derecha: la posición del cursor en el boceto,
mensajes, el archivo actual, el zoom del boceto (1&nbsp;mm = n
píxeles) y el motor: <i>OpenSCAD (listo)</i>, <i>(renderizando&hellip;)</i>
o <i>vista previa integrada</i> cuando OpenSCAD no está instalado.</p>
"""),

        ("toolbars", "Las barras de herramientas", f"""
<p>La <b>barra de herramientas izquierda</b> contiene las herramientas
de dibujo (siempre hay una activa &mdash; Seleccionar por defecto),
las dos herramientas de medición, y los sólidos 3D que se añaden en
un clic. La <b>barra de herramientas principal</b> de arriba se
divide en secciones:</p>
{figure("toolbar_main", "La barra de herramientas principal y sus "
        "secciones.", 900)}
<ul>
<li><b>Archivo</b> &mdash; Nuevo, Abrir, Guardar.</li>
<li><b>Deshacer</b> &mdash; Deshacer y Rehacer.</li>
<li><b>Operaciones</b> &mdash; seis grupos desplegables (más
abajo).</li>
<li><b>Ensamblaje</b> &mdash; Ajustar objetos entre sí (el imán).</li>
<li><b>Boceto</b> &mdash; cuadrícula, ajuste a la cuadrícula,
espaciado de la cuadrícula, el plano del boceto y Encajar boceto.</li>
<li><b>Vista 3D</b> &mdash; Renderizar con OpenSCAD, Encajar en 3D.</li>
<li><b>IA</b> &mdash; el chat del asistente.</li>
</ul>
<h3>Cómo funcionan los grupos de operaciones</h3>
<p>Cada botón de grupo es una familia de herramientas. <b>Haga clic
en el icono</b> y se ejecuta la herramienta mostrada &mdash; la que
usó por última vez en esa familia (se recuerda entre sesiones).
<b>Haga clic en la pequeña flecha</b> junto a él para ver toda la
familia y elegir otra; al pasar el cursor sobre una herramienta de la
lista se muestra su información completa.</p>
<table><tr>
<td>{figure("group_extrude", "Extrusión", 190)}</td>
<td>{figure("group_transform", "Mover y transformar", 190)}</td>
<td>{figure("group_combine", "Combinar", 190)}</td>
</tr><tr>
<td>{figure("group_deform", "Deformar y esculpir", 230)}</td>
<td>{figure("group_character", "Personaje", 260)}</td>
<td>{figure("group_logic", "Repetir y lógica", 190)}</td>
</tr></table>
<p>Las operaciones actúan sobre la <b>selección</b>: seleccione
primero objetos (en el árbol o en el boceto), luego elija la
operación &mdash; los envuelve, así que el árbol muestra, por
ejemplo, <i>Rotación</i> con sus objetos dentro. Agrupar, los bucles y
Si/si no también funcionan sin nada seleccionado: añaden un nodo
vacío en el que arrastrar objetos.</p>
<p>Cada herramienta se describe una por una en el capítulo
<b>Referencia de herramientas</b>.</p>
"""),

        ("insert_menu", "El menú Insertar", f"""
<p>Cada herramienta de las dos barras de herramientas también está en
el menú <b>Insertar</b>, un submenú por grupo &mdash; útil cuando
conoce el nombre de una herramienta pero no su icono, y cada entrada
conserva la información de uso del icono:</p>
<ul>
<li><b>Formas 2D</b> &mdash; línea, rectángulo, círculo, polígono,
texto (las mismas herramientas de dibujo que la barra izquierda; la
marca indica la que está en uso).</li>
<li><b>Sólidos 3D</b> &mdash; cubo, esfera, cilindro, cápsula,
elipsoide, caja redondeada, loft.</li>
<li><b>Extrusión</b>, <b>Mover y transformar</b>, <b>Combinar</b>,
<b>Acabado</b>, <b>Deformar y esculpir</b>, <b>Personaje</b> y
<b>Repetir y lógica</b> &mdash; las familias de operaciones de la
barra de herramientas principal, aplicadas a la selección.</li>
<li><b>Medir y anotar</b>, <b>Ensamblaje</b> (Ajustar objetos
{K("J")}) y <b>Código y archivos</b> (variables, mallas importadas,
código OpenSCAD, chapa metálica).</li>
</ul>
<p>El menú se construye a partir de las mismas tablas que las barras
de herramientas, así que una herramienta nueva aparece en ambos
sitios a la vez.</p>
"""),
        ("exploded", "Vistas explosionadas", f"""
<p>Una <b>vista explosionada</b> separa cada pieza de un ensamblaje
de su centro, para ver cómo encaja todo &mdash; para instrucciones,
para una ficha de Printables, o simplemente para ver qué hay detrás
de qué. Es una forma de <i>mirar</i>: el modelo en sí no se mueve.</p>
<ul>
<li><b>Vista &rsaquo; Vista explosionada &rsaquo; Explosionar el
ensamblaje</b> {K("Ctrl+Shift+X")} la activa y desactiva;
{K("Ctrl+F")} encuadra las piezas separadas. El mismo interruptor
está en la barra de la esquina superior derecha de la vista 3D, con
todas las opciones bajo su flecha.</li>
<li><b>Qué se separa</b>: con una pieza seleccionada, el ensamblaje al
que pertenece &mdash; seleccione una hoja de una bisagra y toda la
bisagra se separa, mientras el resto permanece en su sitio y la
selección sigue a su pieza. Sin nada seleccionado, son las piezas del
documento (o del Objeto que está editando); si un único Grupo u
Objeto las contiene todas, se examina su interior. Una operación
booleana es un solo sólido y nunca se separa. Cuando solo hay una
pieza, la barra de estado lo indica.</li>
<li><b>Distancia</b> 50&ndash;300&nbsp;%: al 100&nbsp;%, cada pieza
se mueve otra vez la distancia que ya la separa del centro.</li>
<li><b>Hacia fuera (radial)</b> dispersa las piezas en todas
direcciones; <b>A lo largo de X / Y / Z</b> las mantiene alineadas
&mdash; una pila de placas explosiona bien a lo largo de Z.</li>
<li>Una pieza es cada fila de nivel superior de Principal (un
Objeto, una instancia, un grupo coloreado); en la pestaña Objeto, son
las subpiezas propias del Objeto.</li>
<li><b>Archivo &rsaquo; Exportar PNG</b> tiene una casilla <b>Vista
explosionada</b>, y <b>Publicar en Printables</b> añade imágenes
explosionadas (isométrica y frontal) para cualquier ensamblaje de dos
o más piezas.</li>
</ul>
"""),
        ("cut-through", "Corte", f"""
<p>El <b>corte</b> secciona la vista 3D con un plano, retira una
mitad y colorea la cara de corte en rojo &mdash; como se ve una
sección CAD &mdash; para que pueda ver cómo está hecha una pieza por
dentro: los agujeros y taladros, el grosor de la pared, una rosca,
cómo encaja una pieza en otra. Como la vista explosionada, es una
forma de <i>mirar</i>: el modelo, sus exportaciones y sus planos
permanecen enteros.</p>
<ul>
<li>Haga clic en las <b>tijeras</b> de la barra de herramientas, o en
<b>Vista &rsaquo; Corte</b> {K("Ctrl+Alt+X")}, o en las tijeras de la
barra de la esquina superior derecha de la vista 3D &mdash; su flecha
lista todas las opciones: el eje, dónde va el corte (un cuarto, la
mitad, tres cuartos) y qué mitad se conserva.</li>
<li>Aparece una barra en la parte inferior de la vista 3D: elija
<b>X</b>, <b>Y</b> o <b>Z</b>, y arrastre el control deslizante para
mover el corte por el modelo; la lectura da su posición en
milímetros.</li>
<li><b>&#x21C4;</b> conserva la otra mitad; <b>&#x2715;</b> (o el
botón de la barra de herramientas de nuevo) muestra el modelo
entero.</li>
<li>Siga orbitando mientras está cortado: la cara roja es la
sección, lo que hay detrás es el interior de la pieza.</li>
<li>Con OpenSCAD instalado, el corte atraviesa la geometría exacta,
así que los agujeros taladrados y las roscas se muestran tal como se
imprimirán.</li>
</ul>
<p>Las imágenes de <b>Archivo &rsaquo; Exportar PNG</b> de la vista
actual muestran el corte; <b>Publicar en Printables</b> y el
<b>Plano</b> siempre usan el modelo entero. Una sección de dibujo
técnico 2D (con rayado, con su línea de corte) está en el
<b>Plano</b>: Insertar &rsaquo; Vista de sección.</p>
"""),
        ("reference", "Referencia de herramientas", "@reference"),

        ("sketching", "Dibujar en 2D", f"""
<p>Las formas 2D son el punto de partida de la mayoría de las piezas:
dibuje el contorno, luego dele profundidad. Elija una herramienta en
la barra izquierda, dibuje en el boceto, y luego afine los números en
Propiedades.</p>
<ul>
<li><b>Rectángulo</b> {K("R")} &mdash; arrastre de esquina a
esquina.</li>
<li><b>Círculo</b> {K("C")} &mdash; pulse en el centro, arrastre hasta
el radio. Un <i>Ángulo</i> de 180 da un semicírculo, 90 un cuarto.</li>
<li><b>Polígono</b> {K("P")} &mdash; haga clic en cada vértice,
doble clic o {K("Enter")} para cerrar, {K("Esc")} para abandonar.</li>
<li><b>Línea</b> {K("L")} &mdash; una barra entre dos puntos, con un
<i>Ancho</i>; se extruye como cualquier forma.</li>
<li><b>Texto</b> {K("T")} &mdash; haga clic para colocarlo, escriba
el texto en Propiedades.</li>
</ul>
<h3>Cuadrícula, ajuste y planos</h3>
<p><b>Cuadrícula</b> muestra la cuadrícula en milímetros;
<b>Ajustar</b> hace que los puntos dibujados caigan en ella; la
casilla <b>Cuadrícula</b> fija el espaciado (hasta 0,01 mm). La
casilla <b>Plano</b> elige en qué plano dibuja: Superior (XY) para
placas y contornos, Frontal (XZ) para perfiles que va a revolucionar,
Lateral (YZ).</p>
<h3>Unidades del documento</h3>
<p>Un modelo está en milímetros salvo que se indique lo contrario:
<b>Editar &rsaquo; Unidades del documento&hellip;</b> permite elegir
nanómetros, micrómetros, centímetros, metros o pulgadas. Cambia cómo
se <i>llaman</i> los números, no el modelo &mdash; una partícula de
100&nbsp;nm se escribe 100 en un documento en nanómetros, y la barra
de estado, la escala, las medidas, las ventanas de Analizar y el
recuadro UNIDADES del Plano muestran todos nm. La masa se calcula a
tamaño real; el tiempo y coste de impresión solo para mm, cm y
pulgadas. Cualquier laminador (slicer) lee un STL como milímetros,
así que Exportar STL pregunta si mantener 1:1 o escalar a milímetros
reales. La unidad se guarda con el documento.</p>
<p>Un modelo también puede representar algo mucho más grande o
pequeño que él mismo. <b>Editar &rsaquo; Escala del documento
(1&nbsp;:&nbsp;N)&hellip;</b> indica cómo se compara con la realidad
&mdash; una Tierra de 60&nbsp;mm es
1&nbsp;:&nbsp;212&nbsp;600&nbsp;000 &mdash; y la escala 3D mide
entonces la realidad en kilómetros y escribe la razón debajo, como en
un mapa. Insertar un planeta o una luna en un documento vacío la
ajusta automáticamente. La escala también sube sola a metros y
kilómetros, así que una calle a tamaño real se lee como 200&nbsp;m, no
200000&nbsp;mm.</p>
<h3>Medir</h3>
<p><b>Medir</b> {K("M")}: haga clic en dos puntos &mdash; la distancia
se muestra en la barra de estado y no se añade nada. <b>Añadir
cota</b> {K("D")}: igual, pero deja una línea de cota en el boceto
(Vista &rsaquo; Borrar cotas las elimina). Ambas se ajustan a
esquinas y aristas. Las formas seleccionadas también muestran su
propio tamaño automáticamente (Vista &rsaquo; Cotas en la
selección).</p>
<h3>Editar formas</h3>
<p>Con <b>Seleccionar</b> {K("V")}: haga clic para seleccionar,
arrastre para mover, arrastre un tirador cuadrado para
redimensionar. Los vértices de un polígono se editan con precisión en
la tabla de puntos de Propiedades. Vista &rsaquo; Encajar boceto
{K("Ctrl+Shift+F")} y Zoom a la selección recuadran la vista.</p>
<p class='tip'><i>Consejo:</i> las formas 2D también se combinan
&mdash; una diferencia de dos círculos hace un anillo, una unión de
rectángulos hace una L &mdash; antes de extruir.</p>
"""),

        ("solids", "Crear sólidos", f"""
<h3>A partir de una forma 2D</h3>
<p>La <b>extrusión lineal</b> empuja las formas 2D seleccionadas
directamente hacia arriba una <i>Altura</i>. El <i>Retorcido</i> gira
la parte superior a medida que sube (un jarrón retorcido), la
<i>Escala</i> encoge o agranda la parte superior (0 hace una punta,
una pirámide), el <i>Centrado</i> extruye igualmente hacia arriba y
hacia abajo.</p>
<p>La <b>extrusión por revolución</b> gira un perfil alrededor del
eje vertical como un torno. Dibuje <i>la mitad</i> de la sección, a la
derecha del eje Y: su X se convierte en el radio y su Y en la
altura. Un perfil que cruza X&nbsp;=&nbsp;0 se pone rojo. Un
<i>Ángulo</i> menor de 360 hace una rebanada.</p>
<p>El <b>barrido a lo largo de una trayectoria</b> hace avanzar un
perfil por una trayectoria 3D &mdash; la herramienta para tuberías,
pasamanos, pasos de cables, muelles y eslabones de cadena (lo que
Blender hace con una curva y un objeto de bisel). Dibuje la sección
alrededor del origen (un círculo para una tubería, un rectángulo para
un pasamanos), aplique el barrido, y luego escriba los <b>Puntos de
la trayectoria</b> en Propiedades. Las esquinas se ingletean; el
<b>Suavizado</b> las redondea en una curva uniforme que aun así pasa
por cada punto. El <b>Grosor de pared</b> lo ahueca en una tubería, el
<b>Bucle cerrado</b> une el final con el principio (una junta tórica),
y <b>Retorcido</b> / <b>Escala</b> actúan a lo largo de toda la
longitud. Visto con la trayectoria viniendo hacia usted y Z hacia
arriba, la x del perfil va a la derecha y su y hacia arriba, igual
que en la Extrusión lineal. Biblioteca &rsaquo; Ejemplos mecánicos
&rsaquo; <i>Tubería y pasamanos</i> muestra los tres.</p>
{figure("sweep", "Una tubería hueca a través de curvas suavizadas, "
        "un pasamanos cuadrado ingleteado y una junta tórica cerrada "
        "&mdash; tres barridos.")}
<h3>Sólidos ya hechos</h3>
<p>La parte inferior de la barra de herramientas izquierda añade un
sólido en un clic: <b>Cubo</b>, <b>Esfera</b>, <b>Cilindro</b> (un
radio superior distinto hace un cono), <b>Cápsula</b> (una varilla
con extremos redondeados entre dos puntos), <b>Elipsoide</b>, <b>Caja
redondeada</b> y <b>Loft</b> (un tubo suave a través de una lista de
secciones transversales). En la pestaña Principal, un sólido nuevo se
convierte en su propia pieza y la pestaña Objeto se abre sobre él; en
la pestaña Objeto, se añade a la pieza que está construyendo.</p>
<p><b>Segmentos</b> fija cuántas facetas forman una forma redonda. El
valor por defecto del documento es la casilla <b>Segmentos comunes
($fn)</b> de la pestaña Principal.</p>
<h3>Otras formas de añadir</h3>
<ul>
<li><b>Insertar &rsaquo; Biblioteca de piezas</b> {K("Ctrl+L")}
&mdash; bridas paramétricas, sujetadores con roscas reales, válvulas,
cristalería, mobiliario.</li>
<li><b>Archivo &rsaquo; Importar malla</b> {K("Ctrl+Shift+I")}
&mdash; archivos STL, OBJ, OFF o 3MF, o arrastre el archivo a la
ventana. La pieza llega como un solo Objeto y la barra de estado da
su tamaño: un STL no tiene unidades, así que una pieza dibujada en
pulgadas o metros puede aparecer mucho más pequeña de lo esperado.
Clic derecho sobre ella &rsaquo; <b>Malla importada</b> para
centrarla, apoyarla en el suelo, o indicar en qué unidad se dibujó el
archivo; sus Propiedades también permiten girarla y escalarla.
Funciona como cualquier otra pieza: ajustarse a sus caras, colorearla,
o restarla de un bloque (el renderizado de OpenSCAD la recorta con
exactitud) para fabricar un soporte que encaje con ella. Mantenga la
malla dentro de la carpeta del documento y el .kcad la guarda con una
ruta relativa, así que la carpeta se puede mover o compartir
completa.</li>
<li><b>Insertar &rsaquo; Código OpenSCAD</b> &mdash; un bloque de
OpenSCAD en bruto (por ejemplo, una llamada a BOSL2) que el motor
renderiza.</li>
</ul>
"""),

        ("combine", "Mover y combinar", f"""
<h3>Mover, girar, redimensionar</h3>
<p>La mayoría de los sólidos tienen su propio <b>X / Y / Z</b> en
Propiedades, y puede arrastrar cualquier pieza en el boceto. El grupo
<b>Mover y transformar</b> en cambio envuelve la selección:
<b>Trasladar</b> (mover según X/Y/Z), <b>Rotar</b> (grados alrededor
de X, luego Y, luego Z, alrededor del origen), <b>Escalar</b>
(factores; 1 = sin cambios) y <b>Reflejar</b> (espejo; el original no
se conserva).</p>
<p class='tip'><i>Consejo:</i> Rotar gira alrededor del origen, así
que gire una pieza <i>antes</i> de alejarla, o describirá un gran
arco.</p>
<h3>Combinar</h3>
<ul>
<li><b>Agrupar (unión)</b> {K("Ctrl+G")} &mdash; varios objetos se
convierten en uno. {K("Ctrl+Shift+G")} desagrupa.</li>
<li><b>Diferencia</b> &mdash; conserva el <b>primer</b> hijo y
recorta de él cada uno de los demás hijos. El orden importa:
seleccione primero el cuerpo. En el árbol, arrastre las filas (o
{K("Ctrl+&uarr;")}/{K("Ctrl+&darr;")}) para cambiar cuál es el
cuerpo.</li>
<li><b>Intersección</b> &mdash; conserva solo donde todos los hijos
se solapan.</li>
</ul>
<p>Clic derecho &rsaquo; <b>Aplicar operación</b> en el árbol ofrece
el resto: <b>Envolvente convexa</b> (envuelve los hijos &mdash; dos
esferas hacen una cápsula), <b>Minkowski</b> (barre una forma
alrededor de otra), <b>Desplazamiento</b> (redondea o mete hacia
adentro las esquinas 2D) y <b>Redondear aristas</b> (una pequeña
esfera de Minkowski que redondea un sólido terminado).</p>
<h3>Redondear aristas &mdash; Redondeo</h3>
<p><b>Redondear aristas</b> (grupo Acabado) es el equivalente al
Fillet de SolidWorks: redondea solo las aristas que elija. Seleccione
el sólido, haga clic en Redondear aristas, y la vista 3D pide
aristas &mdash; <b>haga clic en una arista</b> para redondearla; un
clic en el borde de un cilindro toma todo el borde, y un clic en una
<b>cara</b> redondea cada arista alrededor de esa cara. {K("Esc")}
cuando termine, y luego ajuste el <b>Radio</b> en Propiedades;
<b>Tipo</b> Chaflán corta un plano en lugar de una curva. Una arista
convexa se redondea y una esquina cóncava se rellena. Las aristas se
recuerdan como geometría, así que el redondeo sobrevive a
redimensionar y mover la pieza; si una arista desaparece (la ha
cortado), el redondeo se pone rojo e indica cuál. Clic derecho sobre
el redondeo ▸ <b>Elegir aristas</b> para añadir más.</p>
{figure("fillet", "Redondear aristas: aristas superiores redondeadas, "
        "una arista vertical achaflanada, y el borde de un saliente "
        "redondeado con un clic.")}
<p class='tip'><i>Consejo:</i> una arista solo existe donde una forma
realmente la tiene. Dos cajas que se solapan no tienen arista de
esquina interior hasta que forman un solo sólido, así que para una
esquina interior, dibuje la L como un solo perfil y extrúyalo. Y como
cualquier corte, el redondeo aparece en el renderizado exacto de
OpenSCAD (poco después de cada cambio, o {K("F5")}); <b>Redondear
aristas (antiguo)</b> (clic derecho ▸ Aplicar operación) es la
herramienta más antigua que redondea todas las aristas de una pieza
por la misma cantidad.</p>
<p class='tip'><i>¿Por qué no se recorta mi agujero?</i> La vista
previa integrada instantánea dibuja una Diferencia solo como su
primer hijo. El motor OpenSCAD la recorta de verdad poco después (el
distintivo muestra <i>OpenSCAD</i> o <i>n/n piezas exactas</i>);
pulse {K("F5")} para renderizar de inmediato.</p>
"""),

        ("tree", "Trabajar con el árbol de objetos", f"""
<p>El árbol <i>es</i> el modelo: una fila por paso, con los hijos
sangrados bajo la operación que los envuelve.</p>
<table>
<tr><td>Seleccionar</td><td>clic; Ctrl+clic añade; {K("Tab")} /
{K("Shift+Tab")} (o {K("A")} / {K("Q")}) pasan al objeto
siguiente / anterior</td></tr>
<tr><td>Ocultar / mostrar</td><td>{K("Space")} o clic derecho
&rsaquo; Ocultar. Las filas ocultas se ponen grises y en cursiva, y
todo lo que hay debajo se atenúa.</td></tr>
<tr><td>Renombrar</td><td>clic derecho &rsaquo; Renombrar</td></tr>
<tr><td>Reordenar / mover</td><td>arrastrar y soltar;
{K("Ctrl+&uarr;")} / {K("Ctrl+&darr;")} dentro del mismo padre</td></tr>
<tr><td>Copiar y pegar</td><td>{K("Ctrl+C")} {K("Ctrl+X")}
{K("Ctrl+V")} &mdash; también funciona entre dos ventanas de
KherveCAD</td></tr>
<tr><td>Duplicar / eliminar</td><td>{K("Ctrl+D")} /
{K("Delete")}</td></tr>
<tr><td>Color</td><td>clic derecho &rsaquo; Color&hellip;</td></tr>
</table>
<p>El menú contextual también tiene <b>Aplicar operación</b>,
<b>Agrupar / Desagrupar</b>, <b>Crear objeto</b>, <b>Crear
maestro</b> y, en una pieza, <b>Editar en la pestaña Objeto</b> (o
doble clic sobre ella), <b>Anclajes</b> y <b>Acoplar /
Desacoplar</b>.</p>
<p>Una pieza colocada muestra debajo filas grises adicionales de
<b>Posición</b>, <b>Rotación</b> y <b>Color</b>: reflejan dónde se ha
colocado la pieza (arrastrando, ajustando o escribiendo valores) y no
se pueden editar directamente &mdash; haga clic en ellas para
seleccionar la pieza.</p>
<h3>Nombres que dicen qué es cada cosa</h3>
<p>Un árbol de diez filas todas llamadas <i>Cubo</i> es difícil de
leer. Renombre las filas sobre la marcha, con el formato <b>Cubo
[Cuerpo]</b>: la parte entre corchetes es una etiqueta, y también se
escribe en el programa como un comentario, así que sobrevive a
guardar como .scad y volver a importar. También funciona al revés
&mdash; cuando un asistente (o usted) escribe OpenSCAD con un
comentario al final de una línea, ese comentario se convierte en la
etiqueta:</p>
<pre>color("pink") cube(body, center=true);  // Body
for (px = [-1, 1]) for (py = [-1, 1])  // Legs</pre>
{figure("named_rows", "Filas nombradas a partir de los comentarios "
        "del código: Cube [Body], Cube [Head], For px [Legs]&hellip;",
        430)}
<h3>El rojo significa que algo está roto</h3>
<p>Una fila que no puede funcionar &mdash; una expresión incorrecta,
una extrusión vacía, un sólido 3D dentro de una extrusión, una
revolución que cruza su eje &mdash; se pone <b>roja</b>. Pase el
cursor por encima para ver el motivo; sus líneas también aparecen en
rojo en la pestaña Código. Los propios errores de OpenSCAD se
asocian de vuelta a las filas que los causaron.</p>
"""),

        ("logic", "Variables, expresiones y lógica", f"""
<h3>Variables</h3>
<p>Dé nombre a los tamaños importantes en la pestaña
<b>Variables</b> &mdash; <i>w = 60</i>, <i>wall = 2</i> &mdash; y use
el nombre en cualquier campo: Ancho <code>w</code>, ancho interior
<code>w - 2 * wall</code>. Cambie la variable y todo lo que la usa la
sigue. La casilla <b>Ámbito</b> cambia entre las variables de todo el
documento y las del Objeto que se está editando.</p>
<h3>Expresiones</h3>
<p>Cualquier campo numérico acepta una expresión: <code>+ - * / %
^</code>, comparaciones, <code>a ? b : c</code>, y <code>sin cos tan
sqrt abs min max round floor ceil pow</code>&hellip; (ángulos en
grados). Los vectores también funcionan: <code>size.x</code>,
<code>pts[2]</code>.</p>
<h3>Repetir y elegir</h3>
<ul>
<li>El <b>bucle For</b> repite su contenido. La variable recorre
<i>Desde</i> &rarr; <i>Hasta</i> con un <i>Paso</i>, o una lista de
<i>Valores</i>. Úsela en el contenido: X = <code>i * 20</code> hace
una fila, Rotar Z = <code>i * 60</code> hace un anillo. Un bucle
dentro de otro bucle hace una cuadrícula.</li>
<li>El <b>bucle While</b> se repite mientras se cumple una condición,
actualizando su variable cada vez (por ejemplo, inicio 1, condición
<code>x &lt; 100</code>, actualización <code>x * 2</code>).</li>
<li><b>Si / si no</b> muestra su contenido solo cuando la condición
es verdadera, y su fila <i>Si no</i> en caso contrario &mdash; active
o desactive una característica con una variable, o alterne piezas
dentro de un bucle con <code>i % 2 == 0</code>.</li>
<li>El <b>Patrón</b> repite su contenido como copias sin una variable
de bucle &mdash; el modificador Array de Blender, los patrones
lineal y circular de SolidWorks. <i>Lineal</i> coloca <i>Cantidad</i>
copias con un <i>Paso X/Y/Z</i> (una fila de agujeros; ajuste también
el Paso Z para una escalera recta). <i>Polar</i> las gira alrededor
del <i>Eje</i>: con un <i>Ángulo</i> de 360, las copias se reparten
uniformemente por todo el círculo (<code>360 &middot; i / count</code>
&mdash; un círculo de tornillos); por debajo de 360 <b>cubren</b> el
ángulo, la primera a 0&deg; y la última en el <i>Ángulo</i>
(<code>angle &middot; i / (count &minus; 1)</code> &mdash; cinco
nervios en 90&deg;); <i>Elevación por copia</i> eleva cada copia a lo
largo del eje, así que un muelle o una escalera de caracol son un
solo patrón. <i>Cuadrícula</i> hace <i>Cantidad X &times; Y &times;
Z</i> copias con el paso indicado. Cada campo acepta una expresión.
En el programa es una sola llamada
<code>kcad_pattern(&hellip;) {{ &hellip; }}</code>.</li>
<li>La <b>pieza de chapa metálica</b> (menú Insertar) es una placa
con una <b>pestaña</b> doblada en cualquiera de sus cuatro bordes:
dé a cada borde una longitud y un ángulo de doblez (negativo dobla
hacia abajo), más el grosor de la chapa, el radio de doblez interior
y el <b>factor K</b>. Clic derecho sobre ella &rsaquo;
<b>Desplegar</b> coloca el <b>patrón plano</b> al lado &mdash; el
bruto con la asignación de doblez
<code>(r + K&middot;t)&middot;&theta;</code> en cada doblez y las
líneas de doblez marcadas, y la barra de estado da el tamaño del
bruto &mdash; y <b>Exportar patrón plano DXF</b> lo escribe (capas
CUT y BEND) para una cortadora láser o una plegadora. Un doblez por
borde; una caja, una bandeja, una escuadra, un canal o una U salen
directamente de ella.</li>
</ul>
{figure("pattern", "Un ejemplo por patrón: un círculo de tornillos "
        "polar, una escalera de caracol (polar con elevación), una "
        "escalera recta y una cuadrícula de espigas.")}
<p>Con objetos seleccionados, estas herramientas los envuelven; sin
nada seleccionado, añaden un nodo vacío en el que arrastrar
objetos. El menú <b>Biblioteca &rsaquo; Aprender</b> tiene un
tutorial numerado para cada una.</p>
"""),

        ("assemblies", "Piezas y ensamblajes", f"""
<p>KherveCAD separa <b>construir una pieza</b> de <b>disponer
piezas</b>, como SolidWorks u Onshape:</p>
<ul>
<li>Un <b>Objeto</b> es la definición de una pieza, construida en la
<b>pestaña Objeto</b>. Se convierte en su propio <code>module</code>
de OpenSCAD.</li>
<li>La <b>pestaña Principal</b> es el ensamblaje: <b>instancias</b>
de Objetos, cada una con su propia posición, rotación y color. Un
mismo Objeto se puede colocar muchas veces &mdash; edítelo una vez y
cada copia cambia.</li>
</ul>
<h3>Crear y colocar piezas</h3>
<ul>
<li><b>Insertar &rsaquo; Nuevo objeto</b> {K("Ctrl+Alt+N")}, o el
icono <b>Nuevo</b> (un más dentro de un cuadro) en la pestaña Objeto,
inicia una pieza vacía.</li>
<li>Los iconos de la pestaña Objeto, de izquierda a derecha:
<b>Nuevo</b>, <b>Renombrar</b> (lápiz), <b>Eliminar</b> (papelera
&mdash; el Objeto y cada instancia suya en Principal desaparecen
juntos, y {K("Ctrl+Z")} los trae de vuelta a todos) y <b>A
Principal</b>. Pase el cursor sobre uno para ver su nombre.</li>
<li>La lista de Objetos contiene <b>todos</b> los Objetos del
documento, incluidos los anidados &mdash; los <code>module</code>s de
un programa importado son Objetos aunque un color los envuelva.</li>
<li>Clic derecho en objetos &rsaquo; <b>Crear objeto</b> los convierte
en una pieza.</li>
<li><b>A Principal</b> (el icono de paquete) en la pestaña Objeto, o
clic derecho en Principal &rsaquo; Insertar objeto, coloca otra
instancia.</li>
<li>Arrastre el contorno de una pieza en el boceto para moverla en el
plano elegido, o escriba su X/Y/Z y ángulos en Propiedades.</li>
</ul>
<h3>Ajustar piezas entre sí</h3>
<p>La herramienta <b>Ajustar objetos</b> {K("J")} une dos piezas cara
con cara, como una junta (joint) en Fusion 360:</p>
<ol>
<li>Pulse {K("J")} (o el imán de la barra de herramientas
principal). Un aviso en la vista 3D indica qué hacer clic.</li>
<li>Haga clic en la cara o arista de la pieza que quiere
<b>mover</b>. La cara bajo el cursor se ilumina primero, nombrada
según el anclaje que usará; la que hace clic queda naranja.</li>
<li>Haga clic en la cara de la pieza contra la que debe apoyarse. La
pieza salta a su lugar.</li>
<li>Se abre una pequeña ventana para ajustar: <b>Desplazamiento</b>
(un hueco en mm), <b>Giro</b> (girar sobre la junta), <b>Voltear
180&deg;</b> y <b>Desacoplar</b>.</li>
</ol>
<p>{K("Esc")} (o un clic derecho) cancela. Un ajuste es <b>en
vivo</b>: mueva la pieza base y todo lo que está unido a ella sigue.
Arrastrar una pieza acoplada, o escribir su posición, la desacopla
(la barra de estado lo indica).</p>
<h3>Anclajes y el diálogo Acoplar</h3>
<p>Cada pieza tiene <b>anclajes</b> automáticos &mdash; su origen, los
centros de sus seis caras, doce puntos medios de aristas y ocho
esquinas &mdash; dibujados como marcadores de color cuando la pieza
está seleccionada. Clic derecho en una pieza &rsaquo;
<b>Anclajes</b> para añadir los suyos haciendo clic en el modelo,
para <b>fijar el origen</b> en cualquier anclaje, o para eliminar
uno. Clic derecho &rsaquo; <b>Acoplar&hellip;</b> abre el diálogo
Acoplar, donde elige los dos anclajes por nombre; cada cambio se
previsualiza en vivo y Cancelar lo devuelve todo a su sitio. Más allá
del simple ajuste cara con cara, ofrece los acoples de otros
programas CAD: <b>Enrasado</b> (ambas caras en el mismo sentido),
<b>Concéntrico</b> (la pieza se apoya en el eje de la otra y se
desliza a lo largo de él &mdash; arrastrarla en la vista de boceto
mueve el deslizamiento en lugar de romper el acople), <b>Ángulo</b>
(una bisagra: la pieza girada un ángulo alrededor de la arista del
anclaje), una <b>relación de engranaje</b> (el giro propio de la
pieza sigue al del padre multiplicado por la relación, invertido) y
un <b>rango de desplazamiento</b> (un acople límite: el
desplazamiento o el deslizamiento nunca sale de él).</p>
{figure("dialog_attach", "El diálogo Acoplar: qué anclaje de esta "
        "pieza coincide con qué anclaje de la otra.", 450)}
<p>Dentro de la pestaña Objeto, las mismas herramientas ajustan entre
sí los <b>grupos que componen una sola pieza</b>, así que una pieza
puede ensamblarse a su vez a partir de fragmentos.</p>
"""),

        ("masters", "Copias enlazadas", """
<p>Para usar una misma pieza muchas veces, conviértala en un
<b>Objeto</b> y coloque <b>copias enlazadas</b> de él, cada una con
su propia posición y color. Edite el Objeto y cada copia cambia
&mdash; el ejemplo clásico es un tornillo copiado alrededor de un
círculo de agujeros.</p>
<ol>
<li>Clic derecho en un objeto &rsaquo; <b>Crear objeto</b>, y luego en
Principal, clic derecho &rsaquo; <b>Insertar objeto</b> por cada copia
(o <b>A Principal</b> en la pestaña Objeto).</li>
<li>O clic derecho en cualquier cosa &rsaquo; <b>Copia enlazada</b>:
una copia que sigue al original. Ponga una copia en un bucle For para
colocar muchas.</li>
</ol>
<p>Los documentos antiguos con una pestaña <b>Maestros</b> se abren
con cada maestro convertido en un Objeto y sus copias sin cambios.
Biblioteca &rsaquo; Aprender OpenSCAD &rsaquo; 21 y Mecánica &rsaquo;
Círculo de tornillos muestran ambos.</p>
"""),

        ("collections", "Colecciones", """
<p>Una <b>colección</b> es un conjunto con nombre de piezas que se
muestran, ocultan o bloquean juntas &mdash; <i>Paredes</i>,
<i>Tejado</i>, <i>Mobiliario</i> en una casa, <i>Piezas móviles</i>
en un mecanismo &mdash; sea cual sea el aspecto del árbol. Funciona
como las colecciones de Blender.</p>
<ol>
<li>En Principal, seleccione piezas, clic derecho &rsaquo;
<b>Mover a colección</b> &rsaquo; <b>Nueva colección&hellip;</b> (o
una existente).</li>
<li>Abra la pestaña <b>Colecciones</b>. Haga clic en el <b>ojo</b>
para ocultar o mostrar una colección; <b>Ctrl+clic</b> para mostrar
solo esa colección (de nuevo para mostrar todo). Haga clic en el
<b>candado</b> para que sus piezas no se puedan seleccionar ni
arrastrar por accidente en la vista 2D.</li>
<li>Arrastre piezas de una colección a otra, haga doble clic en un
nombre para renombrarlo, clic derecho para el resto. Eliminar una
colección conserva sus piezas.</li>
</ol>
<p>Ocultar una colección solo cambia lo que muestran las vistas: las
piezas permanecen en el diseño, en el programa y en cada
exportación. Para excluir una pieza del propio modelo, oculte la
pieza (Espacio en el árbol).</p>
"""),

        ("colour", "Color y materiales", """
<p>Clic derecho en un objeto &rsaquo; <b>Color&hellip;</b>, o use el
campo de color en Propiedades. Un color es una fila normal del árbol
(el <code>color()</code> de OpenSCAD) con una <b>opacidad</b> y un
<b>material</b>: Plástico, Metal, Mate, Arcilla, Vidrio, Goma, Piel,
Oro, Cobre o Emisivo (<i>Predeterminado</i> sigue el estilo de
renderizado 3D). El Vidrio es translúcido.</p>
<p>En la pestaña Principal, coloree una instancia directamente: cada
copia de una pieza puede tener su propio color. Los colores y
materiales se guardan con el documento y se exportan en el programa
.scad; el renderizado exacto de OpenSCAD de cada pieza se tiñe con su
color.</p>
"""),

        ("character", "Personajes y formas orgánicas", f"""
<p>Para animales, figuras, plantas y cualquier cosa blanda,
KherveCAD tiene formas y operaciones que van más allá de cajas y
cilindros.</p>
<h3>Sólidos blandos</h3>
<p><b>Cápsula</b> (extremidades, dedos), <b>Elipsoide</b> (cabezas,
cuerpos, huevos), <b>Caja redondeada</b> (bloques blandos) y
<b>Loft</b> (colas, cuellos, cuernos: un tubo a través de una lista
de anillos).</p>
<h3>El grupo Personaje</h3>
<ul>
<li><b>Simetría</b> &mdash; conserva su contenido y su imagen
especular: modele el brazo izquierdo y aparece el derecho, siguiendo
cada edición.</li>
<li><b>Articulación</b> &mdash; gira su contenido alrededor de un
pivote, como un codo. Ponga el pivote en la bisagra, luego doble. Las
articulaciones se anidan, así que un árbol de ellas es un esqueleto
al que se le puede dar pose.</li>
</ul>
<h3>El grupo Deformar y esculpir</h3>
<ul>
<li><b>Fusión suave</b> &mdash; funde las formas de dentro entre sí
como arcilla, con redondeos suaves donde se encuentran. El <i>Radio
de fusión</i> es hasta dónde llega la fusión.</li>
<li><b>Doblar</b>, <b>Retorcer</b>, <b>Ahusar</b> &mdash; curvan,
retuercen o estrechan el contenido a lo largo de un eje.</li>
<li><b>Retícula</b> &mdash; mueva las ocho esquinas de la caja
envolvente y la forma le sigue con suavidad.</li>
<li><b>Subdividir</b> &mdash; suaviza una forma angulosa.</li>
<li><b>Carcasa</b> &mdash; ahueca un sólido en una carcasa de grosor
de pared uniforme (el Solidify de Blender): fije el <b>Grosor de
pared</b>, y <b>Lado abierto</b> arriba / abajo / &plusmn;x / &plusmn;y
para dejar un lado abierto &mdash; un cilindro con open = top es una
taza. Una pared demasiado gruesa para la pieza no deja espacio y pone
la carcasa en rojo. Biblioteca &rsaquo; Mecánica &rsaquo; <i>Taza
hueca</i>.</li>
</ul>
{figure("shell", "Carcasa: un cilindro ahuecado en una taza de "
        "2 mm, abierta por arriba.")}
<table><tr>
<td>{figure("character_tulip", "Flores &rsaquo; Tulipán", 360)}</td>
<td>{figure("character_oak", "Árboles &rsaquo; Roble", 360)}</td>
</tr></table>
<p><b>Biblioteca &#9656; Naturaleza y jardín</b> tiene un jardín de
flores y árboles construidos así &mdash; inserte uno y mire su árbol
para ver cómo.</p>
"""),

        ("view3d", "La vista 3D", f"""
<table>
<tr><td>Orbitar</td><td>arrastrar con el botón izquierdo</td></tr>
<tr><td>Desplazar la vista</td><td>arrastrar con el botón derecho o
central</td></tr>
<tr><td>Zoom</td><td>rueda del ratón</td></tr>
<tr><td>Encuadrar todo</td><td>doble clic, {K("Ctrl+F")} o el botón
Encajar en 3D</td></tr>
<tr><td>Botones</td><td>la barra de la esquina superior derecha:
girar a la izquierda / derecha, desplazar, acercar / alejar (mantener
pulsado repite), <b>Enfocar</b> la pieza seleccionada, <b>Encajar
todo</b></td></tr>
<tr><td>Vistas estándar</td><td>Vista &rsaquo; Cámara 3D:
Isométrica, Superior, Inferior, Frontal, Trasera, Izquierda,
Derecha</td></tr>
</table>
<p><b>Vista &rsaquo; Estilo de renderizado 3D</b> cambia el aspecto
(Sombreado, Mate, Arcilla, Cómic, Metal cepillado, Oro, Cobre,
Alámbrico, Rayos X); <b>Fondo 3D</b> y <b>Proyección 3D</b>
(perspectiva u ortográfica) están al lado. La barra flotante ajusta
el brillo y el contraste. Nada de esto cambia el modelo.</p>
{figure("render_styles", "Cuatro de los estilos de renderizado.")}
<h3>Plataforma y sombra</h3>
<p><b>Vista &rsaquo; Plataforma y sombra 3D</b> (o el botón de
plataforma en la barra de la vista 3D) coloca el modelo sobre una
plataforma redonda y proyecta una sombra suave desde una luz lejana
arriba a la izquierda, como la iluminación de una foto de producto.
La luz sigue a la cámara, así que la sombra siempre cae hacia abajo a
la derecha al girar el modelo. Es solo un aspecto visual &mdash; no
se añade nada al modelo ni a los archivos exportados &mdash; y se
recuerda entre sesiones (permanece activa hasta que la desactive).
Las imágenes exportadas (Archivo &rsaquo; Exportar PNG) la
incluyen.</p>
{figure("stage", "La plataforma y su sombra.")}
<h3>Sombreado de cavidades y líneas de arista</h3>
<p>Dos aspectos tomados de la vista sólida de Blender, ambos bajo el
menú <b>Vista</b>: <b>Renderizado por hardware 3D (OpenGL)</b>
(activado por defecto) dibuja el modelo con la tarjeta gráfica
&mdash; oclusión exacta sea cual sea el tamaño del modelo,
antialiasing, y orbita con fluidez; desactívelo para usar el
dibujante integrado, que también usan Alámbrico y Rayos X.
<b>Sombreado de cavidades 3D</b> oscurece los valles y aclara las
crestas para que la forma se lea de un vistazo, y <b>Líneas de arista
3D</b> (activado por defecto) dibuja las aristas reales del modelo y
su contorno en líneas finas &mdash; un cilindro muestra sus dos
bordes, no sus facetas. Ambos son solo aspectos visuales y se
recuerdan entre sesiones; las imágenes exportadas los incluyen.</p>
<p><b>Escala 3D</b> (activada por defecto) coloca una longitud
redonda &mdash; 1, 2 o 5 veces una potencia de diez &mdash; en la
esquina inferior izquierda de la vista 3D, en la unidad del documento
(Editar &#9656; Unidades del documento), y se redibuja al hacer zoom.
Una imagen en perspectiva no tiene una única escala, así que la
barra es exacta en el punto alrededor del cual orbita la cámara;
cambie a ortográfica y será exacta en todas partes.</p>
{figure("cavity_edges", "La misma pieza sin nada especial "
        "(izquierda) y con sombreado de cavidades y líneas de arista "
        "(derecha).")}
<h3>Vista previa y renderizado exacto</h3>
<p>Cada cambio se redibuja al instante con la <b>vista previa
integrada</b>. Si OpenSCAD está instalado (se incluye con el
instalador), un renderizado <b>exacto</b> sigue poco después, una
pieza cada vez &mdash; el distintivo cuenta <i>n/m piezas exactas</i>.
Los agujeros solo se recortan de verdad en el renderizado exacto.
{K("F5")} renderiza de inmediato.</p>
<p>La vista previa se dibuja en un orden exacto de atrás hacia
delante que se completa por sí solo poco después de cada cambio. Si
la vista alguna vez parece desactualizada, <b>Redibujar</b> (&#x27F3;
en la barra de iluminación) la reconstruye a partir del árbol.</p>
"""),

        ("library", "Biblioteca de piezas y ejemplos", f"""
<h3>Biblioteca de piezas</h3>
<p><b>Insertar &rsaquo; Biblioteca de piezas</b> {K("Ctrl+L")} abre
un catálogo de piezas paramétricas: bridas de vacío CF y KF,
racores, válvulas, bombas, medidores, cámaras y manipuladores, todo
en acero inoxidable; tornillos, pernos y tuercas de M3 a M20 con
roscas reales; cristalería de laboratorio; mobiliario; <b>mobiliario
del hogar</b> para cada habitación de una casa (mesa y sillas de
comedor, sofá, cama, armario, cómoda, una cocina con fregadero,
placa y horno, inodoro, lavabo, bañera y ducha) en una selección de
maderas, telas y colores; ladrillos y sets de Lego; <b>cartas de
juego</b>, una a la vez (elija el palo y luego el valor como tamaño);
<b>macetas</b> en varios colores; y modelos ya hechos en
<b>Escuadras</b>, <b>Coches</b>, <b>Minecraft</b> y
<b>Herramientas</b>. Elija una categoría, una pieza y un tamaño
estándar, ajuste cualquier dimensión, y luego <b>Insertar</b>. La
ventana permanece abierta mientras trabaja. Cada pieza llega como un
Objeto; su construcción está en la pestaña Objeto.</p>
{figure("dialog_library", "La Biblioteca de piezas.", 560)}
<p>El menú <b>Biblioteca</b> inserta las mismas piezas en su tamaño
predeterminado con un clic.</p>
<h3>Ejemplos</h3>
<p>Modelos de ejemplo ya hechos también están en el menú
<b>Biblioteca</b>, cada uno en un submenú marcado <i>Se abre como un
documento, en lugar del suyo</i>: la sección APRENDER al final tiene
<b>Aprender OpenSCAD paso a paso</b> (21 tutoriales numerados, desde
un simple cubo hasta los maestros), <b>Proyectos del curso</b> y
<b>Modelos de muestra</b> (entre ellos un Ferrari 288 GTO
completamente montado); Ingeniería tiene <b>Ejemplos mecánicos</b>
(escuadras, engranajes, rodamientos, poleas, una brida atornillada) y
un punto de partida de vacío bajo Vacío y ultra alto vacío; Casa y
hogar termina con una configuración de escritorio. Abra uno y recorra
su árbol para ver cómo está hecho. Se le pregunta antes de reemplazar
trabajo sin guardar.</p>
<h3>Mecanismos y movimiento</h3>
<p><b>Biblioteca &#9656; Mecanismos y movimiento</b> añade mecanismos
funcionales a su diseño &mdash; un motor y un par de engranajes,
biela-manivela, cremallera y piñón, leva y seguidor, mecanismo de
cuatro barras, tren planetario, una plataforma móvil XY, un elevador
de tijera y un brazo robótico. Cada uno se coloca junto a lo que ya
hay con sus propios controles deslizantes en el panel
<b>Personalizador</b> (Vista &#9656; Personalizador): arrastre uno, o
pulse &#9654; junto a él, y el mecanismo se mueve. Inserte varios y
cada uno conserva sus propias variables (<code>crank_angle</code>,
<code>crank2_angle</code>&hellip;).</p>
"""),

        ("crystals", "Cristales y nanopartículas", """
<p><b>Biblioteca &#9656; Constructor de cristales&hellip;</b>
construye estructuras cristalinas reales a partir de una biblioteca
de 32 estructuras estándar &mdash; metales (cobre, oro, hierro,
titanio&hellip;), semiconductores (silicio, GaAs, GaN), sales,
óxidos (rutilo, anatasa, perovskita, &alpha;-cuarzo) y carbono
(diamante, grafito, h-BN). Cada entrada contiene su red y cada átomo
de su celda unitaria, comprobados con su densidad y longitudes de
enlace publicadas.</p>
<p>Un cristal se construye en tres niveles, cada uno su propio
Objeto:</p>
<table>
<tr><td><b>Celda unitaria</b></td><td>la caja de la red, cada átomo
en su radio covalente y, para compuestos, los poliedros de
coordinación (tetraedros SiO<sub>4</sub> en el cuarzo, octaedros
TiO<sub>6</sub> en el rutilo) dibujados sobre los átomos.</td></tr>
<tr><td><b>Superceldas</b></td><td>un bloque de celdas unitarias
repetido mediante bucles <i>for</i>.</td></tr>
<tr><td><b>Partícula</b></td><td>una esfera, semiesfera, cubo, caja,
cilindro, prisma hexagonal u octaedro rellenado con cada celda cuyo
centro cae dentro &mdash; o, para partículas grandes, con bloques de
N&times;N&times;N celdas. Las columnas de una esfera se apilan
mediante un bucle <i>while</i>.</td></tr>
<tr><td><b>Dispersión</b></td><td>varias partículas repartidas sobre
un área, sin tocarse, cada una apoyada sobre la superficie (una
semiesfera plana sobre ella) y girada al azar &mdash; una dispersión
sobre un sustrato. La partícula se construye una sola vez y se
repite, así que veinte cuestan poco más que una, y la semilla
reproduce siempre la misma disposición.</td></tr>
</table>
<p>El panel cuenta la construcción a medida que la cambia &mdash;
celdas, átomos, poliedros y los triángulos que dibujará la vista 3D
&mdash; y no construirá algo que congelaría la vista: una partícula de
10&nbsp;nm ya contiene decenas de miles de átomos. Dibuje las celdas
como <b>poliedros</b> (unas diez veces más ligero que átomos) o deje
que <b>Automático</b> cambie a bloques.</p>
<p>Los cristales se construyen en <b>nanómetros</b>: un documento
vacío cambia a nm (Editar &#9656; Unidades del documento). El radio,
el tamaño de bloque y el hueco se convierten en variables con nombre
del cristal &mdash; <tt>quartz_r</tt>, <tt>quartz_N</tt> &mdash; así
que la pestaña <b>Variables</b> permite retocar la construcción
después. Un asistente conectado por MCP usa el mismo constructor
(<tt>list_crystals</tt>, <tt>build_crystal</tt>).</p>
<p>Cada cristal también está ya hecho en el menú <b>Biblioteca</b> y
en la Biblioteca de piezas: <b>Cristales (celdas unitarias)</b> y
<b>Cristales (superceldas)</b>, de 2&times;2&times;2 a
6&times;6&times;6 celdas, con un clic.</p>
"""),

        ("molecules", "Moléculas y reacciones", """
<p><b>Biblioteca &#9656; Constructor de compuestos&hellip;</b>
construye moléculas en 3D y escribe reacciones químicas con ellas.</p>
<p>En la pestaña <b>Molécula</b>, elija un compuesto de la biblioteca
&mdash; unos 80, desde el agua y el CO<sub>2</sub> hasta ácidos,
iones, disolventes e hidrocarburos, pasando por glucosa, cafeína y
aspirina &mdash; o escriba cualquier molécula en <b>SMILES</b>, la
notación lineal que usan los químicos (el etanol es <tt>CCO</tt>, el
fenol <tt>c1ccccc1O</tt>, el ion amonio <tt>[NH4+]</tt>). Cada átomo
recibe la forma que le dan sus enlaces y pares solitarios &mdash; el
agua doblada a 104,5&deg;, el metano tetraédrico, el XeF<sub>4</sub>
cuadrado &mdash; y los anillos salen como anillos reales: el benceno
plano, el ciclohexano en forma de silla. Dibújela en <b>bolas y
varillas</b> (cada mitad de un enlace en el color de su átomo,
enlaces dobles y triples como varillas paralelas), en <b>relleno
espacial</b> o como <b>varillas</b>.</p>
<p>En la pestaña <b>Reacción</b>, escriba la ecuación como en el
papel: <tt>2 H2 + O2 -&gt; 2 H2O</tt>, <tt>N2 + 3 H2 &lt;=&gt; 2
NH3</tt>. Omita los números y <b>Equilibrarla</b> los encuentra; el
panel siempre muestra si los átomos y las cargas están equilibrados
antes de construir. La reacción se dispone de izquierda a derecha con
sus coeficientes, signos más, flecha y la fórmula bajo cada molécula.
Las especies son nombres o fórmulas de la biblioteca
(<tt>ethanol</tt>, <tt>H2O</tt>, <tt>SO4^2-</tt>) o
<tt>smiles:</tt>&hellip; para cualquier otra cosa.</p>
<p>Las moléculas se construyen en <b>nanómetros</b>, y cada compuesto
de la biblioteca también está ya hecho en el menú <b>Biblioteca</b>
(familias <b>Moléculas:</b>&hellip;). Un asistente conectado por MCP
usa el mismo constructor (<tt>list_molecules</tt>,
<tt>build_molecule</tt>, <tt>build_reaction</tt>).</p>
"""),

        ("code", "Código OpenSCAD", f"""
<p>La pestaña <b>Código</b> muestra el programa OpenSCAD escrito a
partir del árbol. Seleccionar un objeto resalta sus líneas; los
objetos rotos se tiñen de rojo.</p>
{figure("tab_code", "La pestaña Código para la pieza de la placa con "
        "un agujero.", 430)}
<ul>
<li><b>Editar y aplicar</b>: cambie el texto y pulse <b>Aplicar
código</b> &mdash; se vuelve a leer como objetos reales y
editables.</li>
<li><b>Ámbito</b>: <i>Programa completo</i> u <i>Objeto activo</i>
(solo la pieza abierta en la pestaña Objeto).</li>
<li>La barra de herramientas tiene deshacer/rehacer, cortar/copiar/
pegar y sangría; {K("Tab")} / {K("Shift+Tab")} sangran y quitan la
sangría de las líneas seleccionadas.</li>
</ul>
<h3>Importar y exportar</h3>
<ul>
<li><b>Archivo &rsaquo; Exportar OpenSCAD</b> {K("Ctrl+E")} escribe
un archivo .scad independiente; <b>Importar OpenSCAD</b>
{K("Ctrl+I")} (o abrir un archivo .scad) lo vuelve a leer como
objetos. Exportar &rarr; importar &rarr; exportar da el mismo
programa.</li>
<li>Una llamada que KherveCAD no puede convertir en objetos se
conserva como una fila de <b>código OpenSCAD</b> con exactamente lo
que se escribió: el motor la renderiza, y no se pierde nada al
volver a exportar. Un archivo entero también se puede cargar como un
único bloque en bruto.</li>
<li>Un comentario al final de una línea nombra ese objeto en el
árbol: <code>cube(10);  // Lid</code> se convierte en <b>Cube
[Lid]</b>.</li>
<li><b>Archivo &rsaquo; Importar dibujo 2D</b> lee contornos SVG y
DXF (<code>import()</code>), <b>Importar mapa de alturas</b> una
matriz .dat o una imagen (<code>surface()</code>); los archivos .csg
y .amf también se abren.</li>
</ul>
<h3>El lenguaje OpenSCAD, como objetos</h3>
<p>Cada instrucción de OpenSCAD tiene una fila en el árbol y escribe
de vuelta el mismo código: <b>resize</b>, <b>multmatrix</b>,
<b>render</b>, <b>intersection_for</b>, <b>let</b>, <b>echo</b> y
<b>assert</b> (una aserción falsa se pone roja con su mensaje),
módulos con <code>children()</code>, cálculo vectorial, cadenas de
texto y literales de función. Las expresiones sobre variables siguen
siendo expresiones, así que un programa importado sigue siendo
paramétrico. Clic derecho &rsaquo; <b>Modificador de depuración</b>
fija <code>#</code> (resaltar), <code>%</code> (fondo) o
<code>!</code> (mostrar solo).</p>
<h3>Bibliotecas</h3>
<p><b>Biblioteca &rsaquo; Bibliotecas OpenSCAD</b> instala BOSL2,
MCAD, NopSCADlib, Round-Anything, dotSCAD, threads.scad, Catch'n'Hole
y Gridfinity en su carpeta de bibliotecas de OpenSCAD. Un programa
que empieza con <code>include &lt;BOSL2/std.scad&gt;</code> se abre
entonces aquí: las llamadas de biblioteca se convierten en objetos
cuando es posible y siguen siendo código OpenSCAD cuando no.</p>
<h3>Personalizador</h3>
<p>Comentarios al estilo Customizer de OpenSCAD convierten variables
en controles de la pestaña <b>Variables</b>:</p>
<pre>/* [Size] */
// Box width in mm
width = 40;   // [10:5:200]
lid = "snap"; // [snap, screw, none]</pre>
<p>da un control deslizante y un desplegable en la columna
<i>Ajustar</i>, agrupados y descritos; los comentarios se vuelven a
escribir al exportar.</p>
<h3>Animación</h3>
<p><b>Vista &rsaquo; Animar</b> reproduce un modelo que lee
<code>$t</code> (0 a 1) &mdash; <code>rotate([0, 0, 360 *
$t])</code> &mdash; y exporta sus fotogramas como imágenes.</p>
"""),

        ("features", "Engranajes, roscas, agujeros e impresión", f"""
<p>Las piezas de las bibliotecas más conocidas de OpenSCAD son
objetos en KherveCAD, cada una con sus ajustes en Propiedades y un
módulo OpenSCAD real detrás:</p>
<ul>
<li><b>Insertar &rsaquo; Características mecánicas</b>:
<b>engranajes</b> de evolvente (rectos, helicoidales, en espiga,
internos, cremallera, cónicos, sinfín), <b>roscas</b> (métrica,
trapezoidal, cuadrada, diente de sierra, tubo, botella &mdash; o el
macho que corta una tuerca), <b>agujeros</b> (avellanado, boca ancha,
alojamiento de tuerca, inserto termofusible, ranurado, en forma de
lágrima), moleteados y superficies con textura.</li>
<li><b>Insertar &rsaquo; Formas y patrones</b>: poliedros regulares,
estrellas, polígonos con un radio por vértice, formas de Bézier y de
ruta SVG, paneles de panal.</li>
<li><b>Biblioteca &rsaquo; Impresión 3D</b>: colas de milano,
encajes a presión, bisagras impresas en su sitio y bisagras vivas,
resaltes de inserto, un tapón de botella roscado, sujetacables, cajas
y placas base Gridfinity, bandejas divididas, una carcasa de
electrónica. <b>Movimiento y electrónica</b>: motores NEMA,
perfiles ranurados en T, raíles, poleas GT2, rodamientos,
ventiladores, placas Raspberry Pi y Arduino. También Lego Technic y
paneles generativos.</li>
<li>Clic derecho en una pieza &rsaquo; <b>Dividir para
imprimir</b> corta en dos una pieza demasiado grande para la cama de
impresión, con agujeros de espiga y un pasador.</li>
</ul>
<p>Dos engranajes engranan cuando comparten el módulo y el ángulo de
presión y sus centros están separados m &times; (z<sub>1</sub> +
z<sub>2</sub>) / 2. Para una tuerca, ponga una rosca <i>interna</i>
dentro de una Diferencia con el cuerpo de la tuerca.</p>
"""),

        ("ai", "Asistentes: Claude y el ChatBox", f"""
<h3>Conectar con Claude (sin clave API)</h3>
<p><b>IA &rsaquo; Conectar con Claude (Simple)&hellip;</b> permite
que Claude Desktop, Claude Code, Cursor, Cline, VS Code o LM Studio
construyan directamente en el documento abierto, usando la cuenta
que ya tiene.</p>
<ol>
<li>Marque <b>Permitir que los asistentes se conecten a este
documento</b>.</li>
<li>Deje <b>El asistente puede</b> en <b>Completo</b> (recomendado),
para que también pueda abrir y exportar los archivos que mencione.
<i>Editar</i> lo mantiene dentro del documento abierto; <i>Solo
lectura</i> solo le permite mirar.</li>
<li>En <b>Conectar una aplicación</b>, elija la suya y pulse
<b>Conectar</b>; reinicie esa aplicación.</li>
<li>En su chat, <b>mencione KherveCAD</b>: por ejemplo, «<i>en
KherveCAD, haz una escuadra de 40 mm con dos agujeros M6</i>».</li>
</ol>
<p>El asistente trabaja con objetos reales: lee y edita el árbol,
escribe OpenSCAD que llega como filas editables (etiquetadas, p. ej.
<b>Cube [Body]</b>), inserta piezas de biblioteca, ensambla Objetos y
mira la vista 3D para comprobar su trabajo. Cada uno de sus pasos
equivale a un {K("Ctrl+Z")}. La conexión permanece en este
ordenador.</p>
<p>El asistente etiqueta cada pieza que construye (<b>Cube
[Front-left leg]</b>, <b>Sphere [Left eye]</b>), y cuando convierte
una pieza en un <b>Objeto</b> o un <b>Maestro</b>, le dice qué hizo,
por qué, y en qué pestaña encontrarlo.</p>
<h3>Modelado por instinto</h3>
<p>¿Está construyendo mediante conversación? Haga clic en
<b>Modelado por instinto</b> en el extremo derecho de la barra de
herramientas principal ({K("Ctrl+Shift+M")}, o Vista &rsaquo;
Modelado por instinto): el árbol, las Propiedades, el boceto 2D y las
herramientas de dibujo se pliegan, la barra de herramientas solo
conserva Nuevo, Abrir, Guardar, Deshacer y Rehacer, y el modelo 3D
llena la ventana, así que puede describir la pieza y verla
construirse. Haga clic de nuevo para recuperar todo y editar a mano.
El nombre se inspira en el <i>vibe coding</i> &mdash; construir
software describiéndolo a una IA.</p>
{figure("vibe_model", "Modelado por instinto: solo se muestra la "
        "vista 3D, con su barra de navegación; el interruptor está "
        "iluminado al final de la barra de herramientas.")}
<h3>El ChatBox</h3>
<p><b>IA &rsaquo; ChatBox</b> {K("Ctrl+/")} acopla un chat a la
derecha que funciona con su propia clave API de <b>Claude, Mistral u
Ollama</b> (el botón del engranaje). Describa una pieza, o pegue una
imagen de una; la respuesta se aplica al documento &mdash; dentro de
la pieza que está editando cuando la pestaña Objeto está abierta.
Escriba <b>/help</b> para ver sus comandos.</p>
{figure("chat_panel", "El ChatBox.", 270)}
"""),

        ("files", "Archivos, Git y publicación", f"""
<ul>
<li><b>.kcad</b> es el formato propio de KherveCAD: cada objeto,
color, variable, pieza y ajuste. Guardar {K("Ctrl+S")}, Guardar
como {K("Ctrl+Shift+S")}, Abrir {K("Ctrl+O")}, Abrir reciente.</li>
<li><b>Abrir</b> también acepta programas .scad y mallas (.stl,
.obj, .off, .3mf); arrastrar un archivo a la ventana también
funciona.</li>
<li><b>Exportar STL</b> {K("Ctrl+Shift+E")} para impresión 3D
(exacto con OpenSCAD instalado); <b>Exportar OpenSCAD</b>
{K("Ctrl+E")}.</li>
<li><b>Exportar PNG</b> {K("Ctrl+Alt+E")} guarda una imagen de la
vista 3D con sus colores, estilo e iluminación: la <b>vista
actual</b> exactamente como la muestra la cámara, o <b>todas las
vistas estándar</b> (la isométrica de las cuatro esquinas, tres
cuartos frontal, vista de pájaro, ángulo bajo y desde abajo), un
archivo cada una. Elija un tamaño de hasta 4K, y marque <b>Fondo
transparente</b> para colocar la imagen en una diapositiva o una
página web. Su propia cámara nunca se mueve.</li>
<li><b>Plano</b> {K("Ctrl+Shift+D")} (también en la barra de
herramientas) abre el dibujo técnico 2D del modelo en su propia
ventana. La primera vez, dispone la hoja por sí solo: vistas de tercer
ángulo <b>Frontal, Superior y Derecha</b> y una isométrica a la
mayor escala estándar que encaje, las medidas totales, el diámetro de
cada agujero (<i>3&times; &Oslash;6</i>) con su marca de centro, y un
<b>cajetín</b> ya rellenado &mdash; título, número de plano, material,
la <b>masa</b> calculada a partir del volumen y la densidad del
material, escala, hoja, fecha y quién lo dibujó.
<ul>
<li>Arrastre las vistas para disponerlas (Superior y Derecha se
mantienen alineadas con Frontal); arrastre una cota o una nota por su
etiqueta.</li>
<li>Las herramientas a la izquierda: <b>Cota inteligente</b>
{K("D")} (haga clic en un borde redondo para &Oslash; o R, un borde
recto para su longitud, o dos puntos &mdash; luego colóquela),
cotas horizontal, vertical, alineada, de diámetro, de radio y de
ángulo; <b>notas</b> con líneas de referencia, texto, <b>globos</b>,
marcas y líneas de centro, <b>acabado superficial</b>,
<b>referencias</b> y <b>tolerancias geométricas</b>; líneas,
rectángulos y círculos; y <b>vistas de detalle</b> (un área ampliada
2:1). Los clics se ajustan a esquinas, puntos medios, centros y
aristas.</li>
<li>Arriba: Insertar una vista proyectada, una <b>sección</b>
rayada (su línea de corte dibujada en la vista que corta), una
imagen sombreada del modelo o la <b>lista de piezas</b>; tamaño de
hoja A4&ndash;A0, Letter o Tabloide; la escala; <b>papel blanco o
azul de plano</b>; líneas ocultas; cotado automático; disposición
automática.</li>
<li>Seleccione cualquier cosa para editarla en <b>Propiedades</b>
&mdash; el texto de una cota, su prefijo y tolerancia &plusmn;;
doble clic en el cajetín para rellenarlo.</li>
<li><b>Exportar PDF</b>, <b>DXF</b> (por capas, con tipos de línea
HIDDEN y CENTER reales, en milímetros de hoja), <b>SVG</b> o
<b>PNG</b>, o <b>Imprimir</b>.</li>
</ul>
La hoja se guarda en el .kcad. Después de modificar la pieza,
<b>Actualizar desde el modelo</b> {K("F5")} vuelve a proyectar cada
vista y conserva sus anotaciones. Desactive las líneas ocultas para
piezas roscadas o muy detalladas.</li>
<li><b>Archivo &rsaquo; Mostrar en el explorador de archivos</b>
abre la carpeta del documento; <b>Nueva ventana</b>
{K("Ctrl+Shift+N")} abre un segundo documento.</li>
<li><b>Vista &rsaquo; Añadir imagen de referencia&hellip;</b>
coloca una foto o un dibujo en el plano del boceto para calcarlo; se
muestra en ambas vistas.</li>
</ul>
<h3>Git</h3>
<p>El menú <b>Git</b> versiona la carpeta que contiene su documento:
<b>Commit</b> {K("Ctrl+K")} guarda una instantánea con un mensaje,
<b>Enviar</b> / <b>Extraer</b> sincronizan con GitHub o GitLab, y
<b>Conectar con GitHub / GitLab</b> configura el remoto.</p>
<h3>Publicar en Printables</h3>
<p><b>Archivo &rsaquo; Publicar en Printables&hellip;</b>
{K("Ctrl+Shift+P")} prepara todo para subirlo: archivos STL y 3MF
&mdash; y, para un ensamblaje, <b>un STL por Objeto</b>
(<code>name-Object.stl</code>, cada uno en su propio origen, listo
para imprimir por separado; un Objeto dentro de un color o un grupo
también cuenta, y uno colocado varias veces se escribe una sola
vez) &mdash; el .scad y el .kcad, un ZIP con el código fuente,
imágenes de vista previa pintadas exactamente como la vista 3D (sus
colores, materiales, iluminación, plataforma y sombra) desde ocho
ángulos de tres cuartos (la isométrica frontal-derecha primero, como
portada), una descripción y las respuestas del formulario de
subida. Después abre la página de subida de Printables; la subida
final la hace usted con un clic.</p>
"""),

        ("updates", "Actualizaciones", f"""
<p>KherveCAD se mantiene actualizado a partir de sus publicaciones
en GitHub.</p>
<ul>
<li>Una copia instalada comprueba <b>una vez al día</b>, unos
segundos después de arrancar. Cuando existe una versión más
reciente, una ventana lista <b>qué ha cambiado</b>: las notas de la
versión y cada mejora desde la suya.</li>
<li><b>Descargar e instalar</b> la obtiene en segundo plano (con una
barra de progreso que se puede cancelar), luego cierra KherveCAD,
instala y arranca la nueva versión. Primero se le pregunta si quiere
guardar el trabajo sin guardar.</li>
<li><b>Omitir esta versión</b> detiene el recordatorio solo para esa
versión; <b>Más tarde</b> vuelve a preguntar la próxima vez.</li>
<li><b>Ayuda &rsaquo; Buscar actualizaciones&hellip;</b> comprueba
ahora; <b>Ayuda &rsaquo; Buscar actualizaciones
automáticamente</b> activa o desactiva la comprobación diaria.</li>
</ul>
{figure("dialog_update", "Hay una actualización disponible: qué ha "
        "cambiado, y la opción de instalarla.", 620)}
<p>El número de versión es <b>0.1.<i>N</i></b>, donde <i>N</i> cuenta
los cambios hechos a KherveCAD hasta ahora &mdash; sube en uno con
cada cambio, y la barra de título y Ayuda &rsaquo; Acerca de lo
muestran.</p>
<p class='tip'>Una copia portátil, o KherveCAD ejecutado desde su
código fuente, no se sustituye automáticamente: la ventana de
actualización ofrece entonces la página de descarga.</p>
"""),

        ("checking", "Comprobar una pieza", f"""
<p>El menú <b>Analizar</b> (y el menú contextual del árbol) comprueba
una pieza como lo haría un laminador (slicer) o un programa de CAD,
antes de imprimirla o enviarla. Cada ventana permanece abierta
mientras corrige cosas; <b>Comprobar de nuevo</b> vuelve a
ejecutarla.</p>
<h3>Propiedades de masa</h3>
<p>Volumen, área de superficie, tamaño, centro de masa y caja
envolvente de las piezas seleccionadas (o de todo el documento), más
la <b>masa</b> para un material elegido (PLA, PETG, ABS, resina,
aluminio, acero&hellip;), su <b>coste</b> según su precio por
kilogramo, y un tiempo de impresión <i>aproximado</i>. La masa es la
de una pieza maciza; una impresión con relleno pesa menos.</p>
<h3>Comprobar para impresión 3D</h3>
<p>Cuatro comprobaciones, cada una
<span style='color:#2e8b57'><b>APROBADA</b></span>,
<span style='color:#d08a00'><b>AVISO</b></span> o
<span style='color:#c0392b'><b>FALLO</b></span>:</p>
<ul>
<li><b>Estanqueidad</b> &mdash; la superficie está cerrada y con un
enrollado coherente. Una arista abierta significa que un laminador
podría rellenar el lado equivocado o descartar la pieza; el informe
indica dónde está la primera.</li>
<li><b>Voladizos</b> &mdash; las caras orientadas hacia abajo más
allá del límite (45° por defecto) necesitan soportes. Reoriente la
pieza, añada un chaflán bajo el voladizo, o acepte soportes.</li>
<li><b>Grosor de pared</b> &mdash; las paredes más finas que el
mínimo (0,8 mm, dos anchos de extrusión) pueden no imprimirse o
romperse. Engrósalas, o use una boquilla más fina.</li>
<li><b>Huella</b> &mdash; una pieza alta sobre una base pequeña
vuelca o se despega de la placa: túmbela o añada una falda.</li>
</ul>
<p>Marque <b>Mostrar voladizos y paredes finas en el modelo</b> para
ver las caras problemáticas teñidas en la vista 3D.</p>
{figure("print_check", "Comprobación para impresión 3D en una pieza "
        "en forma de T: la parte inferior de la parte superior es "
        "un voladizo.")}
<h3>Comprobar interferencias</h3>
<p>¿Se solapan dos piezas? Seleccione dos o más piezas (o ninguna,
para cada pieza de Principal) y cada par se informa como <b>sin
contacto</b>, <b>INTERSECCIÓN</b> (con un punto de cruce) o
<b>DENTRO / CONTIENE</b> (una está completamente dentro de la otra).
Dos piezas que solo se tocan están sin contacto. Ejecútela después de
ajustar o mover piezas.</p>
<p class='tip'><i>Consejo:</i> las tres funcionan sobre la malla que
muestra la vista 3D. Hasta que llega el renderizado exacto, una
pieza con una Diferencia muestra sus agujeros sin recortar, y los
resultados lo indican.</p>
"""),

        ("shortcuts", "Atajos de teclado", f"""
<p>En Mac, {K("Ctrl")} es la tecla {K("&#8984; Cmd")}.</p>
<table>
<tr><td colspan='2'><b>Herramientas</b></td></tr>
<tr><td>{K("V")} {K("L")} {K("R")} {K("C")} {K("P")} {K("T")}</td>
<td>Seleccionar, Línea, Rectángulo, Círculo, Polígono, Texto</td></tr>
<tr><td>{K("M")} {K("D")}</td><td>Medir, Añadir cota</td></tr>
<tr><td>{K("J")}</td><td>Ajustar objetos entre sí</td></tr>
<tr><td>{K("Enter")} / {K("Esc")}</td><td>Terminar / abandonar un
polígono; {K("Esc")} también cancela un ajuste</td></tr>
<tr><td colspan='2'><b>Archivo</b></td></tr>
<tr><td>{K("Ctrl+N")} {K("Ctrl+O")} {K("Ctrl+S")}</td><td>Nuevo,
Abrir, Guardar ({K("Ctrl+Shift+S")} Guardar como,
{K("Ctrl+Shift+N")} Nueva ventana)</td></tr>
<tr><td>{K("Ctrl+I")} {K("Ctrl+Shift+I")}</td><td>Importar OpenSCAD,
Importar malla</td></tr>
<tr><td>{K("Ctrl+E")} {K("Ctrl+Shift+E")}</td><td>Exportar OpenSCAD,
Exportar STL</td></tr>
<tr><td>{K("Ctrl+Alt+E")}</td><td>Exportar PNG</td></tr>
<tr><td>{K("Ctrl+Shift+P")}</td><td>Publicar en Printables</td></tr>
<tr><td colspan='2'><b>Editar</b></td></tr>
<tr><td>{K("Ctrl+Z")} {K("Ctrl+Y")}</td><td>Deshacer, Rehacer
(también {K("Ctrl+Shift+Z")})</td></tr>
<tr><td>{K("Ctrl+X")} {K("Ctrl+C")} {K("Ctrl+V")}</td><td>Cortar,
Copiar, Pegar</td></tr>
<tr><td>{K("Ctrl+D")} {K("Delete")}</td><td>Duplicar,
Eliminar</td></tr>
<tr><td>{K("Ctrl+G")} {K("Ctrl+Shift+G")}</td><td>Agrupar,
Desagrupar</td></tr>
<tr><td>{K("Ctrl+&uarr;")} {K("Ctrl+&darr;")}</td><td>Subir / bajar
en el árbol</td></tr>
<tr><td>{K("Tab")} {K("Shift+Tab")} ({K("A")} {K("Q")})</td><td>Objeto
siguiente / anterior</td></tr>
<tr><td>{K("Space")}</td><td>Ocultar / mostrar la selección</td></tr>
<tr><td colspan='2'><b>Insertar y vista</b></td></tr>
<tr><td>{K("Ctrl+Alt+N")}</td><td>Nuevo objeto</td></tr>
<tr><td>{K("Ctrl+L")}</td><td>Biblioteca de piezas</td></tr>
<tr><td>{K("Ctrl++")} {K("Ctrl+-")} {K("Ctrl+0")}</td><td>Acercar,
alejar, restablecer el zoom del boceto</td></tr>
<tr><td>{K("Ctrl+Shift+F")} {K("Ctrl+F")}</td><td>Encajar boceto,
Encajar en 3D</td></tr>
<tr><td>{K("Ctrl+'")} {K("Ctrl+Shift+'")}</td><td>Cuadrícula,
Ajustar a la cuadrícula</td></tr>
<tr><td>{K("F5")}</td><td>Renderizar con OpenSCAD</td></tr>
<tr><td colspan='2'><b>Otros</b></td></tr>
<tr><td>{K("Ctrl+/")}</td><td>ChatBox</td></tr>
<tr><td>{K("Ctrl+K")}</td><td>Commit de Git</td></tr>
<tr><td>{K("F1")}</td><td>Esta guía ({K("Ctrl+F")} busca dentro de
ella)</td></tr>
</table>
"""),

        ("troubleshooting", "Solución de problemas", f"""
<h3>No se muestra un agujero o un corte</h3>
<p>La vista previa instantánea dibuja una Diferencia solo como su
primer hijo. Espere a que el distintivo muestre <i>OpenSCAD</i> o
<i>n/n piezas exactas</i>, o pulse {K("F5")}. Si la barra de estado
dice <i>vista previa integrada</i>, no se encontró OpenSCAD:
instálelo, o indique su ubicación con <b>Editar &rsaquo; Ubicar
OpenSCAD&hellip;</b></p>
<h3>Algo se puso rojo</h3>
<p>Pase el cursor sobre la fila roja: la información indica qué está
mal (un error de escritura en una expresión, un sólido 3D dentro de
una extrusión, un perfil de revolución que cruza el eje&hellip;).
Deshaga con {K("Ctrl+Z")} si no está seguro.</p>
<h3>Una operación no hizo nada</h3>
<p>Las operaciones actúan sobre la selección. Seleccione primero
objetos &mdash; en la pestaña Objeto, selecciónelos en el árbol de
<i>esa</i> pestaña.</p>
<h3>El modelo va lento</h3>
<p>Reduzca los <b>Segmentos comunes ($fn)</b> en la pestaña
Principal (32&ndash;48 es de sobra mientras diseña), o los Segmentos
propios de una forma grande. Orbitar alrededor de un modelo grande
muestra un borrador más ligero que vuelve al detalle completo al
soltar.</p>
<h3>La vista 3D se ve mal</h3>
<p>Pulse <b>Redibujar</b> (&#x27F3;) en la barra de iluminación, o
<b>Encajar en 3D</b> si el modelo está fuera de vista.</p>
<h3>Un asistente no ve KherveCAD</h3>
<p>Compruebe que <b>Permitir que los asistentes se conecten</b> está
marcado en IA &rsaquo; Conectar con Claude, que la aplicación se
reinició después de <b>Conectar</b>, y mencione KherveCAD en el
chat.</p>
<h3>KherveCAD se ha cerrado inesperadamente</h3>
<p>Se escribe un informe en <code>khervecad_crash.log</code> en su
carpeta temporal (<code>%TEMP%</code> en Windows). Por favor,
adjúntelo al informar del problema.</p>
"""),
    ]
