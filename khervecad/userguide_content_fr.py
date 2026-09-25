"""The User Guide's chapters, in French.

Mirrors ``userguide_content.py`` chapter for chapter — same anchors,
same structure, same ``figure()``/``kbd()`` calls — with the prose
translated. Loaded by ``userguide.py`` when the active language is
``fr`` (``language.current_language()``); kept as its own module
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
        ("welcome", "Bienvenue", f"""
<p>KherveCAD est un logiciel de CAO pour celles et ceux qui veulent des
solides réels, imprimables et exportables sans devoir d'abord apprendre
un langage de programmation. Vous dessinez, extrudez, combinez et
disposez des pièces ; en coulisses, chaque étape devient une ligne d'un
programme <b>OpenSCAD</b>, et c'est OpenSCAD qui transforme ce programme
en géométrie exacte.</p>
<p>Une seule idée à retenir : <b>votre modèle est un arbre
d'objets</b>. Chaque outil ajoute une ligne à cet arbre ou en modifie
une. Le programme affiché dans l'onglet <b>Code</b> est généré à partir
de l'arbre, si bien que les deux concordent toujours &mdash; vous
pouvez travailler avec celui que vous préférez.</p>
{figure("window", "La fenêtre de KherveCAD avec un modèle d'exemple "
        "chargé.")}
<table>
<tr><td><b>1</b></td><td><b>Arbre d'objets et onglets</b> &mdash; le
modèle lui-même. Principal (l'assemblage), Objet (la pièce en cours de
construction), Collections, Variables et Code.</td></tr>
<tr><td><b>2</b></td><td><b>Propriétés</b> &mdash; chaque réglage de
l'objet sélectionné : tailles, positions, angles, couleur.</td></tr>
<tr><td><b>3</b></td><td><b>Esquisse 2D</b> &mdash; une grille en
millimètres où dessiner des profils et glisser des pièces en
place.</td></tr>
<tr><td><b>4</b></td><td><b>Aperçu 3D</b> &mdash; le résultat solide.
Orbitez, déplacez et zoomez à la souris.</td></tr>
<tr><td><b>5</b></td><td><b>Outils de dessin et solides</b> &mdash;
outils d'esquisse, mesure et formes 3D en un clic.</td></tr>
<tr><td><b>6</b></td><td><b>Barre d'outils principale</b> &mdash;
fichier, annuler, les opérations (regroupées), l'accrochage, les
réglages d'esquisse et la vue 3D.</td></tr>
</table>
<p><b>La sélection est partagée.</b> Cliquez sur un objet n'importe où
&mdash; arbre, 2D ou 3D &mdash; et il est sélectionné partout à la
fois : le panneau Propriétés affiche ses réglages, l'esquisse en
dessine le contour et la vue 3D le teinte en rouge.</p>
<p><b>Survolez n'importe quelle icône</b> pour une info-bulle qui
explique ce qu'elle fait et comment l'utiliser, étape par étape. Appuyez
sur {K("F1")} pour revenir à ce guide.</p>
"""),

        ("first-part", "Votre première pièce en cinq minutes", f"""
<p>Ce tutoriel réalise une plaque percée &mdash; les quatre gestes qui
construisent la plupart des pièces : <i>dessiner, extruder, ajouter,
découper</i>.</p>

<h3>Étape 1 &mdash; dessiner un rectangle</h3>
<ol>
<li>Choisissez l'outil <b>Rectangle</b> dans la barre d'outils de
gauche (ou appuyez sur {K("R")}).</li>
<li>Dans l'esquisse 2D, cliquez sur un coin, glissez jusqu'à l'autre et
relâchez. La taille s'affiche en direct, en millimètres.</li>
<li>Saisissez des valeurs précises dans <b>Propriétés</b> : Largeur 60,
Hauteur 40.</li>
</ol>
<p>Comme vous avez dessiné dans l'onglet <b>Principal</b>, KherveCAD
transforme la forme en un nouvel <b>Objet</b> (une pièce) et ouvre
l'onglet <b>Objet</b> dessus : les pièces se construisent dans l'onglet
Objet et se disposent dans Principal.</p>
{figure("tutorial_1_rectangle", "Un rectangle, dessiné et dimensionné. "
        "L'onglet Objet s'est ouvert sur la nouvelle pièce.")}

<h3>Étape 2 &mdash; l'extruder en une plaque</h3>
<ol>
<li>Le rectangle sélectionné, ouvrez le groupe <b>Extrusion</b> de la
barre d'outils principale et choisissez <b>Extrusion linéaire</b>.</li>
<li>Dans Propriétés, réglez la <b>Hauteur</b> à 8. Le rectangle est
maintenant une plaque : dans l'arbre, <i>Extrusion linéaire</i>
enveloppe <i>Rectangle</i>.</li>
</ol>
{figure("tutorial_2_extrude", "L'extrusion linéaire enveloppe le "
        "rectangle et lui donne de la hauteur.")}

<h3>Étape 3 &mdash; ajouter un cylindre à l'emplacement du trou</h3>
<ol>
<li>Cliquez sur <b>Cylindre</b> dans la barre d'outils de gauche. Il
apparaît à l'origine, à l'intérieur de la pièce en cours d'édition.</li>
<li>Dans Propriétés, réglez les deux rayons à 8, la Hauteur à 20 et Z à
&minus;6, pour qu'il traverse complètement la plaque.</li>
</ol>
{figure("tutorial_3_cylinder", "Le cylindre traverse la plaque ; il "
        "est sélectionné, donc teinté, et ses réglages sont "
        "affichés.")}

<h3>Étape 4 &mdash; découper le trou</h3>
<ol>
<li>Dans l'arbre, cliquez sur <i>Extrusion linéaire</i>, puis
Ctrl+clic sur <i>Cylindre</i> (le corps d'abord, puis l'outil de
coupe).</li>
<li>Ouvrez le groupe <b>Combiner</b> et choisissez <b>Différence</b>.
Le cylindre est soustrait de la plaque.</li>
</ol>
{figure("tutorial_4_difference", "Différence : le premier objet moins "
        "tous ceux qui suivent. Le trou est découpé par le moteur "
        "OpenSCAD.")}
<p>Voilà une pièce terminée. Enregistrez-la avec {K("Ctrl+S")},
exportez-la pour l'impression 3D avec <b>Fichier &rsaquo; Exporter
STL</b>, ou cliquez sur <b>Vers Principal</b> pour la placer dans un
assemblage. Tout ce que vous avez fait est annulable pas à pas avec
{K("Ctrl+Z")}.</p>
<p class='tip'><i>Astuce :</i> les quatre mêmes gestes, appliqués à
d'autres formes, permettent de réaliser presque n'importe quoi : un
polygone extrudé en équerre, des cercles découpés dans une plaque pour
une bride, du texte extrudé et découpé pour une plaque
signalétique.</p>
"""),

        ("window", "La fenêtre, panneau par panneau", f"""
<h3>Les onglets au-dessus de l'arbre</h3>
<p><b>Principal</b> est l'<i>assemblage</i> : chaque pièce de votre
document, une par ligne, placée là où elle doit être. La case
<b>Segments communs ($fn)</b> en haut règle le lissage de chaque
cercle, sphère et cylindre (plus c'est élevé, plus c'est lisse et
lent) ; décochez-la pour laisser chaque forme utiliser sa propre
valeur.</p>
{figure("tab_main", "Onglet Principal : les pièces du document et "
        "leur placement.", 430)}
<p><b>Objet</b> est l'endroit où une pièce est <i>construite</i>.
Choisissez la pièce dans la liste déroulante, ou <b>+ Nouveau</b> pour
en commencer une ; le bouton crayon la renomme et <b>Vers Principal</b>
en place une autre copie dans l'assemblage. Pendant que cet onglet est
ouvert, les vues 2D et 3D ne montrent que cette pièce, à sa propre
origine.</p>
{figure("tab_object", "Onglet Objet : la construction d'une pièce, "
        "étape par étape.", 430)}
<p><b>Variables</b> est un petit tableur de nombres nommés (<i>w</i>,
<i>wall</i>&hellip;) utilisables dans n'importe quel champ. <b>Code</b>
affiche le programme OpenSCAD et permet de le modifier.</p>
{figure("tab_variables", "Onglet Variables : des valeurs nommées "
        "utilisées par des expressions comme <i>w - 2 * wall</i>.",
        430)}

<h3>Propriétés</h3>
<p>Chaque réglage de l'objet sélectionné, généré selon son type :
tailles, position, angles, segments, couleur, texte. Tout champ
numérique accepte aussi une <b>expression</b> &mdash;
<code>wall * 2</code>, <code>i * 10</code>, <code>cos(a) * r</code>
&mdash; c'est ainsi qu'un modèle devient ajustable. Un polygone
affiche ses sommets sous forme de tableau modifiable.</p>
{figure("properties", "Propriétés d'un cylindre.", 430)}

<h3>L'esquisse 2D</h3>
<p>Une grille en millimètres sur un plan du modèle &mdash;
<b>Dessus (XY)</b>, <b>Face (XZ)</b> ou <b>Côté (YZ)</b>, choisi dans
la barre d'outils principale. Les deux axes ont les couleurs du
gizmo 3D (X rouge, Y vert, Z bleu). Les formes se dessinent ici ; une
forme sélectionnée montre sa taille avec des flèches de cotation et
des poignées carrées pour la redimensionner. Les pièces 3D
apparaissent sous forme de contours remplis que l'on peut glisser. Le
glisser au bouton du milieu déplace la vue, la molette zoome, et
l'échelle en bas à gauche indique la taille d'une case de grille. La
petite barre en haut à droite fait la même chose sans souris : les
flèches font défiler, les loupes zooment (maintenir pour répéter),
<b>Cadrer</b> (&#x25CE;) cadre la pièce sélectionnée où qu'elle soit
&mdash; pratique quand une pièce est loin de l'origine &mdash; et
<b>Tout cadrer</b> montre tout.</p>
{figure("sketch", "L'esquisse 2D : un rectangle sélectionné avec ses "
        "cotes automatiques, et un cercle.")}

<h3>L'aperçu 3D</h3>
<p>Le résultat solide. Le <b>glisser du bouton gauche</b> fait
orbiter, le <b>glisser du bouton droit ou du milieu</b> déplace la
vue, la <b>molette</b> zoome et un <b>double-clic</b> cadre le modèle
entier. La barre flottante en haut à gauche règle la
<b>luminosité</b> et le <b>contraste</b> (&#x27F2; les réinitialise)
et propose <b>Redessiner</b> (&#x27F3;). La barre en haut à droite
tourne le modèle, le déplace, zoome, cadre la pièce sélectionnée
(<b>Cadrer</b>) ou le modèle entier (<b>Tout cadrer</b>). L'étiquette
en bas indique ce que vous regardez : <i>aperçu intégré</i>
(instantané, approximatif) ou <i>OpenSCAD</i> (exact), et combien de
pièces sont déjà exactes.</p>
{figure("view3d_plate", "L'aperçu 3D avec la barre de lumière.")}

<h3>La barre d'état</h3>
<p>De gauche à droite : la position du curseur dans l'esquisse, les
messages, le fichier courant, le zoom de l'esquisse (1&nbsp;mm =
n pixels) et le moteur : <i>OpenSCAD (prêt)</i>, <i>(rendu&hellip;)</i>
ou <i>aperçu intégré</i> quand OpenSCAD n'est pas installé.</p>
"""),

        ("toolbars", "Les barres d'outils", f"""
<p>La <b>barre d'outils de gauche</b> contient les outils de dessin
(un est toujours actif &mdash; Sélectionner par défaut), les deux
outils de mesure, et les solides 3D ajoutés en un clic. La <b>barre
d'outils principale</b> en haut est divisée en sections :</p>
{figure("toolbar_main", "La barre d'outils principale et ses "
        "sections.", 900)}
<ul>
<li><b>Fichier</b> &mdash; Nouveau, Ouvrir, Enregistrer.</li>
<li><b>Annuler</b> &mdash; Annuler et Rétablir.</li>
<li><b>Opérations</b> &mdash; six groupes déroulants (ci-dessous).</li>
<li><b>Assemblage</b> &mdash; Accrocher les objets ensemble
(l'aimant).</li>
<li><b>Esquisse</b> &mdash; grille, accrochage à la grille, espacement
de la grille, plan d'esquisse et Cadrer l'esquisse.</li>
<li><b>Vue 3D</b> &mdash; Rendre avec OpenSCAD, Cadrer en 3D.</li>
<li><b>IA</b> &mdash; le chat de l'assistant.</li>
</ul>
<h3>Le fonctionnement des groupes d'opérations</h3>
<p>Chaque bouton de groupe représente une famille d'outils.
<b>Cliquez sur l'icône</b> pour exécuter l'outil affiché &mdash;
celui que vous avez utilisé en dernier dans cette famille (mémorisé
d'une session à l'autre). <b>Cliquez sur la petite flèche</b> à côté
pour voir toute la famille et en choisir un autre ; survoler un outil
dans la liste affiche son info-bulle complète.</p>
<table><tr>
<td>{figure("group_extrude", "Extrusion", 190)}</td>
<td>{figure("group_transform", "Déplacer et transformer", 190)}</td>
<td>{figure("group_combine", "Combiner", 190)}</td>
</tr><tr>
<td>{figure("group_deform", "Déformer et sculpter", 230)}</td>
<td>{figure("group_character", "Personnage", 260)}</td>
<td>{figure("group_logic", "Répéter et logique", 190)}</td>
</tr></table>
<p>Les opérations agissent sur la <b>sélection</b> : sélectionnez
d'abord des objets (dans l'arbre ou l'esquisse), puis choisissez
l'opération &mdash; elle les enveloppe, si bien que l'arbre affiche
par exemple <i>Rotation</i> avec vos objets à l'intérieur. Grouper,
les boucles et Si/sinon fonctionnent aussi sans rien de sélectionné :
ils ajoutent un nœud vide dans lequel glisser des objets.</p>
<p>Chaque outil est décrit un par un dans le chapitre <b>Référence
des outils</b>.</p>
"""),

        ("insert_menu", "Le menu Insertion", f"""
<p>Chaque outil des deux barres d'outils se trouve aussi dans le
menu <b>Insertion</b>, un sous-menu par groupe &mdash; pratique quand
vous connaissez le nom d'un outil mais pas son icône, et chaque
entrée conserve l'info-bulle explicative de l'icône :</p>
<ul>
<li><b>Formes 2D</b> &mdash; ligne, rectangle, cercle, polygone,
texte (les mêmes outils de dessin que la barre de gauche ; la coche
indique celui en cours d'utilisation).</li>
<li><b>Solides 3D</b> &mdash; cube, sphère, cylindre, capsule,
ellipsoïde, boîte arrondie, loft.</li>
<li><b>Extrusion</b>, <b>Déplacer et transformer</b>,
<b>Combiner</b>, <b>Finition</b>, <b>Déformer et sculpter</b>,
<b>Personnage</b> et <b>Répéter et logique</b> &mdash; les familles
d'opérations de la barre d'outils principale, appliquées à la
sélection.</li>
<li><b>Mesurer et annoter</b>, <b>Assemblage</b> (Accrocher les
objets {K("J")}) et <b>Code et fichiers</b> (variables, maillages
importés, code OpenSCAD, tôlerie).</li>
</ul>
<p>Le menu est construit à partir des tables mêmes que les barres
d'outils, si bien qu'un nouvel outil apparaît aux deux endroits à la
fois.</p>
"""),
        ("exploded", "Vues éclatées", f"""
<p>Une <b>vue éclatée</b> écarte chaque pièce d'un assemblage de son
centre, pour voir comment il s'assemble &mdash; pour des
instructions, une fiche Printables, ou simplement pour voir ce qui se
trouve derrière quoi. C'est une façon de <i>regarder</i> : le modèle
lui-même ne bouge pas.</p>
<ul>
<li><b>Vue &rsaquo; Vue éclatée &rsaquo; Éclater l'assemblage</b>
{K("Ctrl+Shift+X")} l'active et la désactive ; {K("Ctrl+F")} cadre les
pièces écartées. Le même interrupteur se trouve sur la barre en haut
à droite de la vue 3D, avec toutes les options sous sa flèche.</li>
<li><b>Ce qui se sépare</b> : avec une pièce sélectionnée, c'est
l'assemblage auquel elle appartient &mdash; sélectionnez une lame
d'une charnière et toute la charnière s'écarte, tandis que le reste
ne bouge pas et que la sélection suit sa pièce. Sans rien de
sélectionné, ce sont les pièces du document (ou de l'Objet en cours
d'édition) ; un seul Groupe ou Objet qui les contient toutes est
examiné. Une opération booléenne est un solide unique et ne se sépare
jamais. Quand il n'y a qu'une seule pièce, la barre d'état le
signale.</li>
<li><b>Distance</b> 50&ndash;300&nbsp;% : à 100&nbsp;%, chaque pièce
se déplace d'une distance égale à celle qui la sépare déjà du
centre.</li>
<li><b>Vers l'extérieur (radial)</b> disperse les pièces dans toutes
les directions ; <b>Le long de X / Y / Z</b> les garde alignées
&mdash; une pile de plaques s'éclate bien le long de Z.</li>
<li>Une pièce est chaque ligne de premier niveau de Principal (un
Objet, une instance, un groupe coloré) ; dans l'onglet Objet, ce sont
les sous-pièces propres de l'Objet.</li>
<li><b>Fichier &rsaquo; Exporter PNG</b> propose une case <b>Vue
éclatée</b>, et <b>Publier sur Printables</b> ajoute des images
éclatées (isométrique et de face) pour tout assemblage de deux pièces
ou plus.</li>
</ul>
"""),
        ("cut-through", "Coupe", f"""
<p>La <b>Coupe</b> tranche la vue 3D avec un plan, retire une moitié
et colore la face de coupe en rouge &mdash; comme une coupe CAO
&mdash; pour voir comment une pièce est faite à l'intérieur : les
trous et alésages, l'épaisseur des parois, un filetage, comment une
pièce s'emboîte dans une autre. Comme la vue éclatée, c'est une façon
de <i>regarder</i> : le modèle, ses exports et ses plans restent
entiers.</p>
<ul>
<li>Cliquez sur les <b>ciseaux</b> dans la barre d'outils, ou <b>Vue
&rsaquo; Coupe</b> {K("Ctrl+Alt+X")}, ou les ciseaux sur la barre en
haut à droite de la vue 3D &mdash; sa flèche liste chaque option :
l'axe, l'endroit de la coupe (un quart, le milieu, trois quarts) et
la moitié conservée.</li>
<li>Une barre apparaît en bas de la vue 3D : choisissez <b>X</b>,
<b>Y</b> ou <b>Z</b>, et faites glisser le curseur pour déplacer la
coupe dans le modèle ; la lecture donne sa position en
millimètres.</li>
<li><b>&#x21C4;</b> conserve l'autre moitié ; <b>&#x2715;</b> (ou le
bouton de la barre d'outils de nouveau) montre le modèle entier.</li>
<li>Continuez d'orbiter pendant la coupe : la face rouge est la
section, ce qui est derrière est l'intérieur de la pièce.</li>
<li>Avec OpenSCAD installé, la coupe traverse la géométrie exacte,
donc les trous alésés et les filetages apparaissent tels qu'ils
seront imprimés.</li>
</ul>
<p>Les images de <b>Fichier &rsaquo; Exporter PNG</b> pour la vue
courante montrent la coupe ; <b>Publier sur Printables</b> et
<b>Plan</b> utilisent toujours le modèle entier. Une coupe 2D de
dessin technique (hachurée, avec sa ligne de coupe) se trouve dans le
<b>Plan</b> : Insertion &rsaquo; Vue en coupe.</p>
"""),
        ("reference", "Référence des outils", "@reference"),

        ("sketching", "Dessiner en 2D", f"""
<p>Les formes 2D sont le point de départ de la plupart des pièces :
dessinez le contour, puis donnez-lui de la profondeur. Choisissez un
outil dans la barre de gauche, dessinez dans l'esquisse, puis
affinez les valeurs dans Propriétés.</p>
<ul>
<li><b>Rectangle</b> {K("R")} &mdash; glissez d'un coin à
l'autre.</li>
<li><b>Cercle</b> {K("C")} &mdash; cliquez au centre, glissez jusqu'au
rayon. Un <i>Angle</i> de 180 donne un demi-cercle, 90 un quart.</li>
<li><b>Polygone</b> {K("P")} &mdash; cliquez chaque sommet,
double-cliquez ou {K("Enter")} pour fermer, {K("Esc")} pour
abandonner.</li>
<li><b>Ligne</b> {K("L")} &mdash; une barre entre deux points, avec
une <i>Largeur</i> ; elle s'extrude comme n'importe quelle forme.</li>
<li><b>Texte</b> {K("T")} &mdash; cliquez pour placer, saisissez le
texte dans Propriétés.</li>
</ul>
<h3>Grille, accrochage et plans</h3>
<p><b>Grille</b> affiche la grille millimétrique ; <b>Accrocher</b>
fait tomber les points dessinés dessus ; la case <b>Grille</b> règle
l'espacement (jusqu'à 0,01 mm). La case <b>Plan</b> choisit sur quel
plan vous dessinez : Dessus (XY) pour les plaques et empreintes, Face
(XZ) pour les profils à révolutionner, Côté (YZ).</p>
<h3>Unités du document</h3>
<p>Un modèle est en millimètres sauf indication contraire :
<b>Édition &rsaquo; Unités du document&hellip;</b> permet de choisir
nanomètres, micromètres, centimètres, mètres ou pouces. Cela change ce
que les nombres <i>signifient</i>, pas le modèle &mdash; une
particule de 100&nbsp;nm s'écrit 100 dans un document en nanomètres, et
la barre d'état, l'échelle, les mesures, les fenêtres Analyser et la
case UNITÉS du Plan affichent tous nm. La masse est calculée en taille
réelle ; le temps et le coût d'impression uniquement pour mm, cm et
pouces. Un STL est lu comme des millimètres par tous les logiciels de
découpe, donc Exporter STL demande s'il faut garder 1:1 ou mettre à
l'échelle en millimètres réels. L'unité est enregistrée avec le
document.</p>
<p>Un modèle peut aussi représenter quelque chose bien plus grand ou
plus petit que lui-même. <b>Édition &rsaquo; Échelle du document
(1&nbsp;:&nbsp;N)&hellip;</b> indique comment il se compare à la
réalité &mdash; une Terre de 60&nbsp;mm est
1&nbsp;:&nbsp;212&nbsp;600&nbsp;000 &mdash; et l'échelle 3D mesure
alors la réalité en kilomètres et inscrit le rapport en dessous, comme
sur une carte. Insérer une planète ou une lune dans un document vide
la règle automatiquement. L'échelle passe aussi d'elle-même aux mètres
et kilomètres, si bien qu'une rue à l'échelle réelle affiche
200&nbsp;m, et non 200000&nbsp;mm.</p>
<h3>Mesurer</h3>
<p><b>Mesurer</b> {K("M")} : cliquez deux points &mdash; la distance
s'affiche dans la barre d'état et rien n'est ajouté. <b>Ajouter une
cote</b> {K("D")} : de même, mais laisse une ligne de cote sur
l'esquisse (Vue &rsaquo; Effacer les cotes les supprime). Les deux
s'accrochent aux coins et aux arêtes. Les formes sélectionnées
affichent aussi automatiquement leur propre taille (Vue &rsaquo; Cotes
sur sélection).</p>
<h3>Modifier des formes</h3>
<p>Avec <b>Sélectionner</b> {K("V")} : cliquez pour sélectionner,
glissez pour déplacer, glissez une poignée carrée pour
redimensionner. Les sommets d'un polygone se modifient précisément
dans le tableau de points de Propriétés. Vue &rsaquo; Cadrer
l'esquisse {K("Ctrl+Shift+F")} et Zoomer sur la sélection recadrent la
vue.</p>
<p class='tip'><i>Astuce :</i> les formes 2D se combinent aussi
&mdash; une différence de deux cercles fait un anneau, une union de
rectangles fait un L &mdash; avant même d'extruder.</p>
"""),

        ("solids", "Créer des solides", f"""
<h3>À partir d'une forme 2D</h3>
<p>L'<b>extrusion linéaire</b> pousse les formes 2D sélectionnées tout
droit vers le haut d'une <i>Hauteur</i>. La <i>Torsion</i> fait
tourner le haut en montant (un vase torsadé), l'<i>Échelle</i> réduit
ou agrandit le haut (0 fait une pointe, une pyramide), le
<i>Centrage</i> extrude également vers le haut et vers le bas.</p>
<p>L'<b>extrusion en révolution</b> fait tourner un profil autour de
l'axe vertical comme un tour. Dessinez la <i>moitié</i> de la section,
à droite de l'axe Y : son X devient le rayon et son Y la hauteur. Un
profil qui traverse X&nbsp;=&nbsp;0 devient rouge. Un <i>Angle</i>
inférieur à 360 fait une tranche.</p>
<p>Le <b>balayage le long d'un chemin</b> fait avancer un profil le
long d'un chemin 3D &mdash; l'outil pour les tuyaux, mains courantes,
passages de câbles, ressorts et maillons de chaîne (ce que Blender
fait avec une courbe et un objet de biseau). Dessinez la section
autour de l'origine (un cercle pour un tuyau, un rectangle pour une
main courante), appliquez le balayage, puis saisissez les
<b>Points du chemin</b> dans Propriétés. Les angles sont coupés à
l'onglet ; le <b>Lissage</b> les arrondit en une courbe régulière qui
passe quand même par chaque point. L'<b>Épaisseur de paroi</b> le
creuse en tuyau, la <b>Boucle fermée</b> relie la fin au début (un
joint torique), et <b>Torsion</b> / <b>Échelle</b> agissent sur toute
la longueur. Vu avec le chemin venant vers vous et Z vers le haut, le
x du profil va vers la droite et son y vers le haut, comme pour
l'extrusion linéaire. Bibliothèque &rsaquo; Exemples mécaniques
&rsaquo; <i>Tuyau et main courante</i> montre les trois.</p>
{figure("sweep", "Un tuyau creux à travers des courbes lissées, une "
        "main courante carrée à onglets et un joint torique fermé "
        "&mdash; trois balayages.")}
<h3>Solides prêts à l'emploi</h3>
<p>Le bas de la barre d'outils de gauche ajoute un solide en un
clic : <b>Cube</b>, <b>Sphère</b>, <b>Cylindre</b> (un rayon supérieur
différent fait un cône), <b>Capsule</b> (une tige aux bouts arrondis
entre deux points), <b>Ellipsoïde</b>, <b>Boîte arrondie</b> et
<b>Loft</b> (un tube lisse à travers une liste de sections). Dans
l'onglet Principal, un nouveau solide devient sa propre pièce et
l'onglet Objet s'ouvre dessus ; dans l'onglet Objet, il est ajouté à
la pièce en cours de construction.</p>
<p><b>Segments</b> règle le nombre de facettes d'une forme ronde. La
valeur par défaut du document est la case <b>Segments communs
($fn)</b> de l'onglet Principal.</p>
<h3>Autres façons d'ajouter</h3>
<ul>
<li><b>Insertion &rsaquo; Bibliothèque de pièces</b> {K("Ctrl+L")}
&mdash; brides paramétriques, fixations à filetages réels, vannes,
verrerie, mobilier.</li>
<li><b>Fichier &rsaquo; Importer un maillage</b> {K("Ctrl+Shift+I")}
&mdash; fichiers STL, OBJ, OFF ou 3MF, ou glissez le fichier sur la
fenêtre. La pièce arrive comme un seul Objet et la barre d'état donne
sa taille : un STL n'a pas d'unités, donc une pièce dessinée en pouces
ou en mètres peut apparaître bien trop petite. Clic droit dessus
&rsaquo; <b>Maillage importé</b> pour le centrer, le poser au sol, ou
indiquer l'unité de dessin du fichier ; ses Propriétés permettent
aussi de le tourner et de le mettre à l'échelle. Il fonctionne comme
n'importe quelle autre pièce : s'accrocher à ses faces, le colorer, ou
le soustraire d'un bloc (le rendu OpenSCAD le découpe exactement) pour
fabriquer un support qui lui correspond exactement. Gardez le
maillage dans le dossier du document et le .kcad le stocke par un
chemin relatif, si bien que le dossier peut être déplacé ou partagé
dans son ensemble.</li>
<li><b>Insertion &rsaquo; Code OpenSCAD</b> &mdash; un bloc
d'OpenSCAD brut (par exemple un appel BOSL2) que le moteur rend.</li>
</ul>
"""),

        ("combine", "Déplacer et combiner", f"""
<h3>Déplacer, tourner, redimensionner</h3>
<p>La plupart des solides ont leurs propres <b>X / Y / Z</b> dans
Propriétés, et vous pouvez glisser n'importe quelle pièce dans
l'esquisse. Le groupe <b>Déplacer et transformer</b> enveloppe plutôt
la sélection : <b>Translation</b> (déplacer selon X/Y/Z),
<b>Rotation</b> (degrés autour de X, puis Y, puis Z, autour de
l'origine), <b>Échelle</b> (facteurs ; 1 = inchangé) et <b>Miroir</b>
(réflexion ; l'original n'est pas conservé).</p>
<p class='tip'><i>Astuce :</i> la Rotation tourne autour de l'origine,
donc tournez une pièce <i>avant</i> de l'éloigner, sinon elle décrira
un grand arc.</p>
<h3>Combiner</h3>
<ul>
<li><b>Grouper (union)</b> {K("Ctrl+G")} &mdash; plusieurs objets
n'en font plus qu'un. {K("Ctrl+Shift+G")} dégroupe.</li>
<li><b>Différence</b> &mdash; conserve le <b>premier</b> enfant et
découpe chaque autre enfant hors de lui. L'ordre compte : sélectionnez
d'abord le corps. Dans l'arbre, faites glisser les lignes (ou
{K("Ctrl+&uarr;")}/{K("Ctrl+&darr;")}) pour changer lequel est le
corps.</li>
<li><b>Intersection</b> &mdash; ne conserve que là où tous les
enfants se superposent.</li>
</ul>
<p>Clic droit &rsaquo; <b>Appliquer une opération</b> dans l'arbre
propose le reste : <b>Enveloppe convexe</b> (enveloppe les enfants
&mdash; deux sphères font une capsule), <b>Minkowski</b> (balaie une
forme autour d'une autre), <b>Décalage</b> (arrondit ou rentre les
coins 2D) et <b>Arrondir les arêtes</b> (une petite sphère de
Minkowski qui arrondit un solide terminé).</p>
<h3>Arrondir des arêtes &mdash; Congé</h3>
<p><b>Arrondir des arêtes</b> (groupe Finition) est l'équivalent du
Fillet de SolidWorks : arrondit seulement les arêtes choisies.
Sélectionnez le solide, cliquez sur Arrondir des arêtes, et la vue 3D
demande des arêtes &mdash; <b>cliquez sur une arête</b> pour
l'arrondir ; un clic sur le pourtour d'un cylindre prend tout le
pourtour, et un clic sur une <b>face</b> arrondit chaque arête autour
de cette face. {K("Esc")} une fois terminé, puis réglez le
<b>Rayon</b> dans Propriétés ; <b>Type</b> Chanfrein coupe un plat au
lieu d'une courbe. Une arête convexe est arrondie et un angle rentrant
est comblé. Les arêtes sont mémorisées comme géométrie, donc le congé
survit au redimensionnement et au déplacement de la pièce ; si une
arête disparaît (vous l'avez coupée), le congé devient rouge et
indique laquelle. Clic droit sur le congé ▸ <b>Choisir des
arêtes</b> pour en ajouter d'autres.</p>
{figure("fillet", "Arrondir des arêtes : arêtes supérieures "
        "arrondies, une arête verticale chanfreinée, et le pourtour "
        "d'un bossage arrondi en un clic.")}
<p class='tip'><i>Astuce :</i> une arête n'existe que là où une forme
la possède réellement. Deux boîtes qui se superposent n'ont pas
d'arête d'angle rentrant tant qu'elles ne forment qu'un seul solide,
donc pour un angle intérieur, dessinez le L comme un seul profil et
extrudez-le. Et comme toute découpe, l'arrondi apparaît dans le rendu
OpenSCAD exact (peu après chaque changement, ou {K("F5")}) ; <b>Arrondir
les arêtes (ancien)</b> (clic droit ▸ Appliquer une opération) est
l'outil plus ancien qui arrondit toutes les arêtes d'une pièce du
même montant.</p>
<p class='tip'><i>Pourquoi mon trou n'est-il pas découpé ?</i> L'aperçu
intégré instantané dessine une Différence comme son premier enfant
seulement. Le moteur OpenSCAD la découpe réellement peu après (le
badge affiche <i>OpenSCAD</i> ou <i>n/n pièces exactes</i>) ; appuyez
sur {K("F5")} pour rendre immédiatement.</p>
"""),

        ("tree", "Travailler avec l'arbre d'objets", f"""
<p>L'arbre <i>est</i> le modèle : une ligne par étape, les enfants
indentés sous l'opération qui les enveloppe.</p>
<table>
<tr><td>Sélectionner</td><td>cliquer ; Ctrl+clic ajoute ;
{K("Tab")} / {K("Shift+Tab")} (ou {K("A")} / {K("Q")}) passent à
l'objet suivant / précédent</td></tr>
<tr><td>Masquer / afficher</td><td>{K("Space")} ou clic droit
&rsaquo; Masquer. Les lignes masquées deviennent grises et italiques,
et tout ce qui se trouve en dessous est estompé.</td></tr>
<tr><td>Renommer</td><td>clic droit &rsaquo; Renommer</td></tr>
<tr><td>Réordonner / déplacer</td><td>glisser-déposer ;
{K("Ctrl+&uarr;")} / {K("Ctrl+&darr;")} au sein du même
parent</td></tr>
<tr><td>Copier et coller</td><td>{K("Ctrl+C")} {K("Ctrl+X")}
{K("Ctrl+V")} &mdash; fonctionne aussi entre deux fenêtres
KherveCAD</td></tr>
<tr><td>Dupliquer / supprimer</td><td>{K("Ctrl+D")} /
{K("Delete")}</td></tr>
<tr><td>Couleur</td><td>clic droit &rsaquo; Couleur&hellip;</td></tr>
</table>
<p>Le menu contextuel propose aussi <b>Appliquer une opération</b>,
<b>Grouper / Dégrouper</b>, <b>Créer un objet</b>, <b>Créer un
maître</b> et, sur une pièce, <b>Modifier dans l'onglet Objet</b> (ou
double-cliquer dessus), <b>Ancrages</b> et <b>Attacher /
Détacher</b>.</p>
<p>Une pièce placée affiche en dessous des lignes grisées
supplémentaires <b>Position</b>, <b>Rotation</b> et <b>Couleur</b> :
elles reflètent où la pièce a été placée (par glisser, accrochage ou
saisie) et ne peuvent pas être modifiées elles-mêmes &mdash;
cliquez dessus pour sélectionner la pièce.</p>
<h3>Des noms qui disent ce que sont les choses</h3>
<p>Un arbre de dix lignes toutes nommées <i>Cube</i> est difficile à
lire. Renommez les lignes au fur et à mesure, sous la forme <b>Cube
[Corps]</b> : la partie entre crochets est une étiquette, également
écrite dans le programme comme commentaire, donc elle survit à un
enregistrement en .scad puis une nouvelle importation. Cela
fonctionne aussi dans l'autre sens &mdash; quand un assistant (ou
vous-même) écrit de l'OpenSCAD avec un commentaire en fin de ligne, ce
commentaire devient l'étiquette :</p>
<pre>color("pink") cube(body, center=true);  // Body
for (px = [-1, 1]) for (py = [-1, 1])  // Legs</pre>
{figure("named_rows", "Des lignes nommées à partir des commentaires "
        "du code : Cube [Body], Cube [Head], For px [Legs]&hellip;",
        430)}
<h3>Le rouge signale une erreur</h3>
<p>Une ligne qui ne peut pas fonctionner &mdash; une expression
incorrecte, une extrusion vide, un solide 3D à l'intérieur d'une
extrusion, un profil en révolution traversant son axe &mdash;
devient <b>rouge</b>. Survolez-la pour connaître la raison ; ses
lignes sont aussi rouges dans l'onglet Code. Les propres erreurs
d'OpenSCAD sont associées aux lignes qui les ont provoquées.</p>
"""),

        ("logic", "Variables, expressions et logique", f"""
<h3>Variables</h3>
<p>Donnez un nom aux tailles importantes dans l'onglet
<b>Variables</b> &mdash; <i>w = 60</i>, <i>wall = 2</i> &mdash; puis
utilisez ce nom dans n'importe quel champ : Largeur <code>w</code>,
largeur intérieure <code>w - 2 * wall</code>. Changez la variable et
tout ce qui l'utilise suit. La case <b>Portée</b> bascule entre les
variables du document et celles de l'Objet en cours d'édition.</p>
<h3>Expressions</h3>
<p>Tout champ numérique accepte une expression : <code>+ - * / %
^</code>, des comparaisons, <code>a ? b : c</code>, et <code>sin cos
tan sqrt abs min max round floor ceil pow</code>&hellip; (angles en
degrés). Les vecteurs fonctionnent aussi : <code>size.x</code>,
<code>pts[2]</code>.</p>
<h3>Répéter et choisir</h3>
<ul>
<li>La <b>boucle For</b> répète son contenu. La variable parcourt
<i>De</i> &rarr; <i>À</i> par <i>Pas</i>, ou une liste de
<i>Valeurs</i>. Utilisez-la dans le contenu : X = <code>i * 20</code>
fait une rangée, Rotation Z = <code>i * 60</code> fait un anneau. Une
boucle dans une boucle fait une grille.</li>
<li>La <b>boucle While</b> se répète tant qu'une condition est vraie,
en mettant à jour sa variable à chaque fois (par exemple départ 1,
condition <code>x &lt; 100</code>, mise à jour <code>x * 2</code>).</li>
<li><b>Si / sinon</b> n'affiche son contenu que lorsque la condition
est vraie, et sa ligne <i>Sinon</i> autrement &mdash; activez ou
désactivez une fonctionnalité avec une variable, ou alternez des
pièces dans une boucle avec <code>i % 2 == 0</code>.</li>
<li>L'<b>Aménagement (Pattern)</b> répète son contenu en copies sans
variable de boucle &mdash; le modificateur Array de Blender, les
aménagements linéaire et circulaire de SolidWorks. <i>Linéaire</i>
place <i>Nombre</i> copies avec un <i>Pas X/Y/Z</i> (une rangée de
trous ; réglez aussi le Pas Z pour un escalier droit).
<i>Polaire</i> les fait tourner autour de l'<i>Axe</i> : avec un
<i>Angle</i> de 360, les copies se répartissent également sur tout le
cercle (<code>360 &middot; i / count</code> &mdash; un cercle de
boulons) ; en dessous de 360 elles <b>couvrent</b> l'angle, la
première à 0&deg; et la dernière à l'<i>Angle</i>
(<code>angle &middot; i / (count &minus; 1)</code> &mdash; cinq
nervures sur 90&deg;) ; <i>Élévation par copie</i> soulève chaque
copie le long de l'axe, si bien qu'un ressort ou un escalier en
colimaçon n'est qu'un seul aménagement. <i>Grille</i> fait
<i>Nombre X &times; Y &times; Z</i> copies au pas indiqué. Chaque
champ accepte une expression. Dans le programme, c'est un seul appel
<code>kcad_pattern(&hellip;) {{ &hellip; }}</code>.</li>
<li>La <b>pièce de tôlerie</b> (menu Insertion) est une plaque avec
une <b>patte</b> pliée sur n'importe lequel de ses quatre bords :
donnez à chaque bord une longueur et un angle de pli (négatif pour
plier vers le bas), plus l'épaisseur de la tôle, le rayon de pli
intérieur et le <b>facteur K</b>. Clic droit dessus &rsaquo;
<b>Déplier</b> dispose le <b>patron à plat</b> à côté &mdash; le
brut avec l'allocation de pli
<code>(r + K&middot;t)&middot;&theta;</code> à chaque pli et les
lignes de pliage marquées, et la barre d'état donne la taille du
brut &mdash; et <b>Exporter le patron à plat en DXF</b> l'écrit
(calques CUT et BEND) pour une découpe laser ou une plieuse. Un pli
par bord ; une boîte, un plateau, une équerre, un profilé en U ou en
C en sortent directement.</li>
</ul>
{figure("pattern", "Un exemple par aménagement : un cercle de boulons "
        "polaire, un escalier en colimaçon (polaire avec élévation), "
        "un escalier droit et une grille de chevilles.")}
<p>Avec des objets sélectionnés, ces outils les enveloppent ; sans
rien de sélectionné, ils ajoutent un nœud vide dans lequel glisser des
objets. Le menu <b>Bibliothèque &rsaquo; Apprendre</b> propose un
tutoriel numéroté pour chacun.</p>
"""),

        ("assemblies", "Pièces et assemblages", f"""
<p>KherveCAD sépare <b>la construction d'une pièce</b> de
<b>la disposition des pièces</b>, comme SolidWorks ou Onshape :</p>
<ul>
<li>Un <b>Objet</b> est la définition d'une pièce, construite dans
l'<b>onglet Objet</b>. Il devient son propre <code>module</code>
OpenSCAD.</li>
<li>L'<b>onglet Principal</b> est l'assemblage : des <b>instances</b>
d'Objets, chacune avec sa propre position, rotation et couleur. Un
même Objet peut être placé plusieurs fois &mdash; modifiez-le une fois
et chaque copie change.</li>
</ul>
<h3>Créer et placer des pièces</h3>
<ul>
<li><b>Insertion &rsaquo; Nouvel objet</b> {K("Ctrl+Alt+N")}, ou
l'icône <b>Nouveau</b> (un plus dans une boîte) de l'onglet Objet,
démarre une pièce vide.</li>
<li>Les icônes de l'onglet Objet, de gauche à droite : <b>Nouveau</b>,
<b>Renommer</b> (crayon), <b>Supprimer</b> (corbeille &mdash; l'Objet
et chacune de ses instances dans Principal disparaissent ensemble, et
{K("Ctrl+Z")} les ramène toutes) et <b>Vers Principal</b>. Survolez
une icône pour voir son nom.</li>
<li>La liste des Objets contient <b>chaque</b> Objet du document, y
compris ceux imbriqués &mdash; les <code>module</code>s d'un
programme importé sont des Objets même quand une couleur les
enveloppe.</li>
<li>Clic droit sur des objets &rsaquo; <b>Créer un objet</b> les
transforme en une pièce.</li>
<li><b>Vers Principal</b> (l'icône de paquet) dans l'onglet Objet, ou
clic droit dans Principal &rsaquo; Insérer un objet, place une autre
instance.</li>
<li>Glissez le contour d'une pièce dans l'esquisse pour la déplacer
sur le plan choisi, ou saisissez son X/Y/Z et ses angles dans
Propriétés.</li>
</ul>
<h3>Accrocher des pièces ensemble</h3>
<p>L'outil <b>Accrocher les objets</b> {K("J")} joint deux pièces
face à face, comme une liaison (joint) dans Fusion 360 :</p>
<ol>
<li>Appuyez sur {K("J")} (ou l'aimant de la barre d'outils
principale). Une bannière sur la vue 3D indique quoi cliquer.</li>
<li>Cliquez sur la face ou l'arête de la pièce à <b>déplacer</b>. La
face sous le curseur s'allume d'abord, nommée d'après l'ancrage
qu'elle utilisera ; celle sur laquelle vous cliquez reste orange.</li>
<li>Cliquez sur la face de la pièce contre laquelle elle doit
s'appuyer. La pièce se met en place instantanément.</li>
<li>Une petite fenêtre s'ouvre pour affiner : <b>Décalage</b> (un
espace en mm), <b>Rotation propre</b> (tourner autour de la liaison),
<b>Retourner 180&deg;</b> et <b>Détacher</b>.</li>
</ol>
<p>{K("Esc")} (ou un clic droit) annule. Un accrochage est <b>vivant</b> :
déplacez la pièce de base et tout ce qui y est attaché suit. Glisser
une pièce attachée, ou saisir sa position, la détache (la barre
d'état le signale).</p>
<h3>Ancrages et la boîte de dialogue Attacher</h3>
<p>Chaque pièce a des <b>ancrages</b> automatiques &mdash; son
origine, les centres de ses six faces, douze milieux d'arêtes et huit
coins &mdash; dessinés comme des marqueurs colorés quand la pièce est
sélectionnée. Clic droit sur une pièce &rsaquo; <b>Ancrages</b> pour
en ajouter un en cliquant sur le modèle, pour <b>définir l'origine</b>
sur n'importe quel ancrage, ou pour en supprimer un. Clic droit
&rsaquo; <b>Attacher&hellip;</b> ouvre la boîte de dialogue Attacher,
où l'on choisit les deux ancrages par leur nom ; chaque changement se
prévisualise en direct et Annuler remet tout en place. Au-delà de la
simple liaison face à face, elle propose les liaisons d'autres
logiciels de CAO : <b>Affleurant</b> (les deux faces dans le même
sens), <b>Concentrique</b> (la pièce repose sur l'axe de l'autre et y
glisse &mdash; la glisser dans la vue d'esquisse déplace le glissement
au lieu de rompre la liaison), <b>Angle</b> (une charnière : la pièce
tournée d'un angle autour de l'arête de l'ancrage), un <b>rapport
d'engrenage</b> (la rotation propre de la pièce suit celle du parent
multipliée par le rapport, inversée) et une <b>plage de décalage</b>
(une liaison limitée : le décalage ou le glissement ne la dépasse
jamais).</p>
{figure("dialog_attach", "La boîte de dialogue Attacher : quel "
        "ancrage de cette pièce rencontre quel ancrage de l'autre.",
        450)}
<p>À l'intérieur de l'onglet Objet, les mêmes outils accrochent
entre eux les <b>groupes qui composent une seule pièce</b>, si bien
qu'une pièce peut elle-même être assemblée à partir de morceaux.</p>
"""),

        ("masters", "Copies liées", """
<p>Pour utiliser une même pièce plusieurs fois, faites-en un
<b>Objet</b> et placez-en des <b>copies liées</b>, chacune avec sa
propre position et sa propre couleur. Modifiez l'Objet et chaque
copie change &mdash; l'exemple classique est un boulon copié autour
d'un cercle de perçage.</p>
<ol>
<li>Clic droit sur un objet &rsaquo; <b>Créer un objet</b>, puis dans
Principal, clic droit &rsaquo; <b>Insérer un objet</b> pour chaque
copie (ou <b>Vers Principal</b> dans l'onglet Objet).</li>
<li>Ou clic droit sur n'importe quoi &rsaquo; <b>Copie liée</b> : une
copie qui suit l'original. Placez une copie dans une boucle For pour
en placer plusieurs.</li>
</ol>
<p>Les anciens documents avec un onglet <b>Maîtres</b> s'ouvrent avec
chaque maître transformé en Objet et ses copies inchangées.
Bibliothèque &rsaquo; Apprendre OpenSCAD &rsaquo; 21 et Mécanique
&rsaquo; Cercle de perçage montrent les deux.</p>
"""),

        ("collections", "Collections", """
<p>Une <b>collection</b> est un ensemble nommé de pièces que l'on
affiche, masque ou verrouille ensemble &mdash; <i>Murs</i>,
<i>Toit</i>, <i>Mobilier</i> dans une maison, <i>Pièces mobiles</i>
dans un mécanisme &mdash; quelle que soit l'apparence de l'arbre. Cela
fonctionne comme les collections de Blender.</p>
<ol>
<li>Dans Principal, sélectionnez des pièces, clic droit &rsaquo;
<b>Déplacer vers la collection</b> &rsaquo; <b>Nouvelle
collection&hellip;</b> (ou une existante).</li>
<li>Ouvrez l'onglet <b>Collections</b>. Cliquez sur l'<b>œil</b> pour
masquer ou afficher une collection ; <b>Ctrl+clic</b> dessus pour
n'afficher qu'elle seule (de nouveau pour tout afficher). Cliquez sur
le <b>cadenas</b> pour que ses pièces ne puissent pas être
sélectionnées ou glissées par accident dans la vue 2D.</li>
<li>Glissez des pièces d'une collection à une autre, double-cliquez
sur un nom pour le renommer, clic droit pour le reste. Supprimer une
collection conserve ses pièces.</li>
</ol>
<p>Masquer une collection ne change que ce que les vues affichent :
les pièces restent dans la conception, dans le programme et dans
chaque export. Pour exclure une pièce du modèle lui-même, masquez la
pièce (Espace dans l'arbre).</p>
"""),

        ("colour", "Couleur et matériaux", """
<p>Clic droit sur un objet &rsaquo; <b>Couleur&hellip;</b>, ou
utilisez le champ couleur de Propriétés. Une couleur est une ligne
ordinaire de l'arbre (le <code>color()</code> d'OpenSCAD) avec une
<b>opacité</b> et un <b>matériau</b> : Plastique, Métal, Mat,
Argile, Verre, Caoutchouc, Peau, Or, Cuivre ou Émissif (<i>Par
défaut</i> suit le style de rendu 3D). Le Verre est translucide.</p>
<p>Dans l'onglet Principal, colorez directement une instance : chaque
copie d'une pièce peut avoir sa propre couleur. Les couleurs et
matériaux sont enregistrés avec le document et exportés dans le
programme .scad ; le rendu OpenSCAD exact de chaque pièce est teinté
de sa couleur.</p>
"""),

        ("character", "Personnages et formes organiques", f"""
<p>Pour les animaux, les personnages, les plantes et tout ce qui est
souple, KherveCAD propose des formes et opérations qui vont au-delà
des boîtes et des cylindres.</p>
<h3>Solides souples</h3>
<p><b>Capsule</b> (membres, doigts), <b>Ellipsoïde</b> (têtes, corps,
œufs), <b>Boîte arrondie</b> (blocs souples) et <b>Loft</b> (queues,
cous, cornes : un tube à travers une liste d'anneaux).</p>
<h3>Le groupe Personnage</h3>
<ul>
<li><b>Symétrie</b> &mdash; conserve son contenu et son image miroir :
modélisez le bras gauche et le droit apparaît, en suivant chaque
modification.</li>
<li><b>Articulation</b> &mdash; fait tourner son contenu autour d'un
pivot, comme un coude. Placez le pivot sur la charnière, puis
pliez. Les articulations s'emboîtent, si bien qu'un arbre
d'articulations forme un squelette que l'on peut poser.</li>
</ul>
<h3>Le groupe Déformer et sculpter</h3>
<ul>
<li><b>Fusion lisse</b> &mdash; fond les formes intérieures ensemble
comme de l'argile, avec des congés lisses là où elles se rencontrent.
Le <i>Rayon de fusion</i> détermine la portée de la fusion.</li>
<li><b>Courber</b>, <b>Torsion</b>, <b>Effiler</b> &mdash; courbent,
tordent ou rétrécissent le contenu le long d'un axe.</li>
<li><b>Treillis</b> &mdash; déplace les huit coins de la boîte
englobante et la forme suit en douceur.</li>
<li><b>Subdiviser</b> &mdash; lisse une forme anguleuse.</li>
<li><b>Coque</b> &mdash; creuse un solide en une coquille d'épaisseur
uniforme (le Solidify de Blender) : réglez l'<b>Épaisseur de
paroi</b>, et <b>Côté ouvert</b> haut / bas / &plusmn;x / &plusmn;y
pour laisser un côté ouvert &mdash; un cylindre avec open = top est
une tasse. Une paroi trop épaisse pour la pièce ne laisse plus de
place et fait passer la coque en rouge. Bibliothèque &rsaquo;
Mécanique &rsaquo; <i>Tasse creuse</i>.</li>
</ul>
{figure("shell", "Coque : un cylindre creusé en une tasse de "
        "2 mm, ouverte en haut.")}
<table><tr>
<td>{figure("character_tulip", "Fleurs &rsaquo; Tulipe", 360)}</td>
<td>{figure("character_oak", "Arbres &rsaquo; Chêne", 360)}</td>
</tr></table>
<p><b>Bibliothèque &#9656; Nature et jardin</b> contient un jardin de
fleurs et d'arbres construits ainsi &mdash; insérez-en un et regardez
son arbre pour voir comment.</p>
"""),

        ("view3d", "La vue 3D", f"""
<table>
<tr><td>Orbiter</td><td>glisser du bouton gauche</td></tr>
<tr><td>Déplacer la vue</td><td>glisser du bouton droit ou du
milieu</td></tr>
<tr><td>Zoomer</td><td>molette de la souris</td></tr>
<tr><td>Tout cadrer</td><td>double-clic, {K("Ctrl+F")} ou le bouton
Cadrer en 3D</td></tr>
<tr><td>Boutons</td><td>la barre en haut à droite : tourner à gauche
/ à droite, déplacer, zoomer avant / arrière (maintenir pour
répéter), <b>Cadrer</b> sur la pièce sélectionnée, <b>Tout
cadrer</b></td></tr>
<tr><td>Vues standard</td><td>Vue &rsaquo; Caméra 3D : Isométrique,
Dessus, Dessous, Face, Arrière, Gauche, Droite</td></tr>
</table>
<p><b>Vue &rsaquo; Style de rendu 3D</b> change l'apparence (Ombré,
Mat, Argile, Cartoon, Métal brossé, Or, Cuivre, Fil de fer, Rayons X) ;
<b>Fond 3D</b> et <b>Projection 3D</b> (perspective ou orthographique)
se trouvent juste à côté. La barre flottante règle la luminosité et le
contraste. Rien de tout cela ne change le modèle.</p>
{figure("render_styles", "Quatre des styles de rendu.")}
<h3>Plateau et ombre</h3>
<p><b>Vue &rsaquo; Plateau et ombre 3D</b> (ou le bouton plateau de la
barre de la vue 3D) pose le modèle sur un plateau rond et projette une
ombre douce à partir d'une lumière lointaine en haut à gauche, comme
un éclairage de photo produit. La lumière suit la caméra, donc l'ombre
tombe toujours vers le bas à droite quand vous tournez le modèle. C'est
purement visuel &mdash; rien n'est ajouté au modèle ni aux fichiers
exportés &mdash; et c'est mémorisé d'une session à l'autre (actif
jusqu'à ce que vous le désactiviez). Les images exportées (Fichier
&rsaquo; Exporter PNG) l'incluent.</p>
{figure("stage", "Le plateau et son ombre.")}
<h3>Ombrage des cavités et lignes d'arête</h3>
<p>Deux apparences empruntées à la vue solide de Blender, toutes deux
sous le menu <b>Vue</b> : <b>Rendu matériel 3D (OpenGL)</b> (activé par
défaut) dessine le modèle avec la carte graphique &mdash; occlusion
exacte quelle que soit la taille du modèle, anticrénelée, et l'orbite
est fluide ; désactivez-le pour utiliser le moteur de dessin intégré,
également utilisé par Fil de fer et Rayons X. <b>Ombrage des cavités
3D</b> assombrit les creux et éclaircit les crêtes pour que la forme se
lise d'un coup d'œil, et <b>Lignes d'arête 3D</b> (activé par défaut)
dessine les vraies arêtes du modèle et son contour en fines lignes
&mdash; un cylindre montre ses deux cercles, pas ses facettes. Les
deux sont purement visuels et mémorisés d'une session à l'autre ; les
images exportées les incluent.</p>
<p><b>Échelle 3D</b> (activée par défaut) place une longueur ronde
&mdash; 1, 2 ou 5 fois une puissance de dix &mdash; en bas à gauche de
la vue 3D, dans l'unité du document (Édition &#9656; Unités du
document), et la redessine au fil du zoom. Une image en perspective
n'a pas d'échelle unique, donc l'échelle n'est exacte qu'au point
autour duquel la caméra orbite ; passez en orthographique et elle
devient exacte partout.</p>
{figure("cavity_edges", "La même pièce simple (à gauche) et avec "
        "l'ombrage des cavités et les lignes d'arête (à droite).")}
<h3>Aperçu et rendu exact</h3>
<p>Chaque changement redessine instantanément avec l'<b>aperçu
intégré</b>. Si OpenSCAD est installé (il est inclus avec
l'installeur), un rendu <b>exact</b> suit peu après, une pièce à la
fois &mdash; le badge compte <i>n/m pièces exactes</i>. Les trous ne
sont vraiment découpés que dans le rendu exact. {K("F5")} rend
immédiatement.</p>
<p>L'aperçu se dessine dans un ordre exact d'arrière vers l'avant qui
se termine de lui-même peu après chaque changement. Si la vue semble
un jour obsolète, <b>Redessiner</b> (&#x27F3; sur la barre de lumière)
la reconstruit à partir de l'arbre.</p>
"""),

        ("library", "Bibliothèque de pièces et exemples", f"""
<h3>Bibliothèque de pièces</h3>
<p><b>Insertion &rsaquo; Bibliothèque de pièces</b> {K("Ctrl+L")}
ouvre un catalogue de pièces paramétriques : brides à vide CF et KF,
raccords, vannes, pompes, jauges, chambres et manipulateurs, tous en
acier inoxydable ; boulons, vis et écrous de M3 à M20 avec de vrais
filetages ; verrerie de laboratoire ; mobilier ; <b>mobilier pour la
maison</b> pour chaque pièce d'une habitation (table à manger et
chaises, canapé, lit, armoire, commode, une cuisine avec évier,
plaque et four, toilettes, lavabo, baignoire et douche), avec un
choix de bois, tissus et couleurs ; briques et sets Lego ; <b>cartes
à jouer</b>, une à la fois (choisissez la couleur, puis la valeur
comme taille) ; des <b>pots</b> en plusieurs couleurs ; et des
modèles prêts à l'emploi dans <b>Supports</b>, <b>Voitures</b>,
<b>Minecraft</b> et <b>Outils</b>. Choisissez une catégorie, une
pièce et une taille standard, ajustez n'importe quelle dimension,
puis <b>Insérer</b>. La fenêtre reste ouverte pendant que vous
travaillez. Chaque pièce arrive comme un Objet ; sa construction se
trouve dans l'onglet Objet.</p>
{figure("dialog_library", "La Bibliothèque de pièces.", 560)}
<p>Le menu <b>Bibliothèque</b> insère les mêmes pièces à leur taille
par défaut en un clic.</p>
<h3>Exemples</h3>
<p>Des modèles d'exemple prêts à l'emploi se trouvent aussi dans le
menu <b>Bibliothèque</b>, chacun dans un sous-menu marqué <i>S'ouvre
comme un document, à la place du vôtre</i> : la section APPRENDRE en
bas contient <b>Apprendre OpenSCAD pas à pas</b> (21 tutoriels
numérotés, d'un simple cube aux maîtres), <b>Projets de cours</b> et
<b>Modèles de démonstration</b> (parmi lesquels une Ferrari 288 GTO
entièrement assemblée) ; Ingénierie propose des <b>Exemples
mécaniques</b> (équerres, engrenages, roulements, poulies, une bride
boulonnée) et un point de départ pour le vide sous Vide et
ultravide ; Maison et intérieur se termine par un aménagement de
bureau. Ouvrez-en un et parcourez son arbre pour voir comment il est
fait. Le travail non enregistré vous est demandé avant d'être
remplacé.</p>
<h3>Mécanismes et mouvement</h3>
<p><b>Bibliothèque &#9656; Mécanismes et mouvement</b> ajoute des
mécanismes fonctionnels à votre conception &mdash; un moteur et une
paire d'engrenages, un ensemble bielle-manivelle, une crémaillère et
un pignon, une came et son suiveur, un mécanisme à quatre barres, un
train planétaire, une plateforme mobile XY, un ciseau élévateur et un
bras robotisé. Chacun se place à côté de ce qui existe déjà avec ses
propres curseurs dans le panneau <b>Personnalisation</b> (Vue
&#9656; Personnalisation) : faites-en glisser un, ou appuyez sur
&#9654; à côté, et le mécanisme se met en mouvement. Insérez-en
plusieurs et chacun garde ses propres variables
(<code>crank_angle</code>, <code>crank2_angle</code>&hellip;).</p>
"""),

        ("crystals", "Cristaux et nanoparticules", """
<p><b>Bibliothèque &#9656; Constructeur de cristal&hellip;</b>
construit de vraies structures cristallines à partir d'une
bibliothèque de 32 structures standard &mdash; métaux (cuivre, or,
fer, titane&hellip;), semi-conducteurs (silicium, GaAs, GaN), sels,
oxydes (rutile, anatase, pérovskite, &alpha;-quartz) et carbone
(diamant, graphite, h-BN). Chaque entrée contient son réseau et
chaque atome de sa maille, vérifiés par rapport à sa densité et ses
longueurs de liaison publiées.</p>
<p>Un cristal se construit sur trois niveaux, chacun son propre
Objet :</p>
<table>
<tr><td><b>Maille élémentaire</b></td><td>la boîte du réseau, chaque
atome à son rayon covalent et, pour les composés, les polyèdres de
coordination (tétraèdres SiO<sub>4</sub> dans le quartz, octaèdres
TiO<sub>6</sub> dans le rutile) dessinés sur les atomes.</td></tr>
<tr><td><b>Supercellule</b></td><td>un bloc de mailles élémentaires
répété par des boucles <i>for</i>.</td></tr>
<tr><td><b>Particule</b></td><td>une sphère, demi-sphère, cube,
boîte, cylindre, prisme hexagonal ou octaèdre rempli de chaque
maille dont le centre se trouve à l'intérieur &mdash; ou, pour les
grosses particules, de blocs de N&times;N&times;N mailles. Les
colonnes d'une sphère sont empilées par une boucle
<i>while</i>.</td></tr>
<tr><td><b>Dispersion</b></td><td>plusieurs particules réparties sur
une zone, sans se toucher, chacune posée sur la surface (une
demi-sphère à plat dessus) et tournée aléatoirement &mdash; une
dispersion sur un substrat. La particule est construite une seule
fois puis répétée, donc vingt coûtent à peine plus qu'une, et la
graine reproduit toujours le même arrangement.</td></tr>
</table>
<p>Le panneau compte la construction au fil de vos modifications
&mdash; mailles, atomes, polyèdres et triangles que la vue 3D va
dessiner &mdash; et ne construira pas ce qui figerait la vue : une
particule de 10&nbsp;nm contient déjà des dizaines de milliers
d'atomes. Dessinez les mailles en <b>polyèdres</b> (environ dix fois
plus léger que des atomes) ou laissez <b>Automatique</b> passer à des
blocs.</p>
<p>Les cristaux se construisent en <b>nanomètres</b> : un document
vide passe en nm (Édition &#9656; Unités du document). Le rayon, la
taille de bloc et l'écart deviennent des variables nommées d'après le
cristal &mdash; <tt>quartz_r</tt>, <tt>quartz_N</tt> &mdash; si bien
que l'onglet <b>Variables</b> permet de retoucher la construction par
la suite. Un assistant connecté via MCP utilise le même constructeur
(<tt>list_crystals</tt>, <tt>build_crystal</tt>).</p>
<p>Chaque cristal est aussi prêt à l'emploi dans le menu
<b>Bibliothèque</b> et la Bibliothèque de pièces : <b>Cristaux
(mailles élémentaires)</b> et <b>Cristaux (supercellules)</b>, de
2&times;2&times;2 à 6&times;6&times;6 mailles, en un clic.</p>
"""),

        ("molecules", "Molécules et réactions", """
<p><b>Bibliothèque &#9656; Constructeur de composés&hellip;</b>
construit des molécules en 3D et écrit des réactions chimiques avec
elles.</p>
<p>Dans l'onglet <b>Molécule</b>, choisissez un composé dans la
bibliothèque &mdash; environ 80, de l'eau et du CO<sub>2</sub> aux
acides, ions, solvants et hydrocarbures, jusqu'au glucose, à la
caféine et à l'aspirine &mdash; ou saisissez n'importe quelle
molécule en <b>SMILES</b>, la notation linéaire des chimistes
(l'éthanol est <tt>CCO</tt>, le phénol <tt>c1ccccc1O</tt>, l'ion
ammonium <tt>[NH4+]</tt>). Chaque atome reçoit la forme donnée par ses
liaisons et ses doublets non liants &mdash; l'eau coudée à
104,5&deg;, le méthane tétraédrique, XeF<sub>4</sub> carré &mdash; et
les cycles ressortent comme de vrais cycles : le benzène plan, le
cyclohexane chaise. Dessinez-la en <b>boules et bâtonnets</b> (chaque
moitié d'une liaison dans la couleur de son atome, doubles et triples
liaisons comme des bâtonnets parallèles), en <b>remplissage
spatial</b> ou en <b>bâtonnets</b>.</p>
<p>Dans l'onglet <b>Réaction</b>, écrivez l'équation comme sur le
papier : <tt>2 H2 + O2 -&gt; 2 H2O</tt>, <tt>N2 + 3 H2 &lt;=&gt;
2 NH3</tt>. Omettez les nombres et <b>Équilibrer</b> les trouve ; le
panneau indique toujours si les atomes et les charges sont
équilibrés avant de construire. La réaction est disposée de gauche à
droite avec ses coefficients, signes plus, flèche et la formule sous
chaque molécule. Les espèces sont des noms ou formules de la
bibliothèque (<tt>ethanol</tt>, <tt>H2O</tt>, <tt>SO4^2-</tt>) ou
<tt>smiles:</tt>&hellip; pour tout le reste.</p>
<p>Les molécules se construisent en <b>nanomètres</b>, et chaque
composé de la bibliothèque est aussi prêt à l'emploi dans le menu
<b>Bibliothèque</b> (familles <b>Molécules :</b>&hellip;). Un
assistant connecté via MCP utilise le même constructeur
(<tt>list_molecules</tt>, <tt>build_molecule</tt>,
<tt>build_reaction</tt>).</p>
"""),

        ("code", "Code OpenSCAD", f"""
<p>L'onglet <b>Code</b> affiche le programme OpenSCAD généré à partir
de l'arbre. Sélectionner un objet met en surbrillance ses lignes ; les
objets en erreur sont teintés en rouge.</p>
{figure("tab_code", "L'onglet Code pour la pièce plaque percée.",
        430)}
<ul>
<li><b>Modifier et appliquer</b> : changez le texte et appuyez sur
<b>Appliquer le code</b> &mdash; il est relu en objets réels et
modifiables.</li>
<li><b>Portée</b> : <i>Programme entier</i> ou <i>Objet actif</i>
(seulement la pièce ouverte dans l'onglet Objet).</li>
<li>La barre d'outils propose annuler/rétablir, couper/copier/coller
et l'indentation ; {K("Tab")} / {K("Shift+Tab")} indentent et
désindentent les lignes sélectionnées.</li>
</ul>
<h3>Importer et exporter</h3>
<ul>
<li><b>Fichier &rsaquo; Exporter OpenSCAD</b> {K("Ctrl+E")} écrit un
fichier .scad autonome ; <b>Importer OpenSCAD</b> {K("Ctrl+I")} (ou
ouvrir un fichier .scad) le relit en objets. Exporter &rarr; importer
&rarr; exporter donne le même programme.</li>
<li>Un appel que KherveCAD ne peut pas transformer en objets est
conservé comme une ligne de <b>code OpenSCAD</b> avec exactement ce
qui a été écrit : le moteur le rend, et rien n'est perdu lors d'un
nouvel export. Un fichier entier peut aussi être chargé comme un
unique bloc brut.</li>
<li>Un commentaire en fin de ligne nomme cet objet dans l'arbre :
<code>cube(10);  // Lid</code> devient <b>Cube [Lid]</b>.</li>
<li><b>Fichier &rsaquo; Importer un dessin 2D</b> lit des contours SVG
et DXF (<code>import()</code>), <b>Importer une carte de hauteur</b>
une matrice .dat ou une image (<code>surface()</code>) ; les fichiers
.csg et .amf s'ouvrent aussi.</li>
</ul>
<h3>Le langage OpenSCAD, sous forme d'objets</h3>
<p>Chaque instruction d'OpenSCAD a une ligne dans l'arbre et réécrit
le même code : <b>resize</b>, <b>multmatrix</b>, <b>render</b>,
<b>intersection_for</b>, <b>let</b>, <b>echo</b> et <b>assert</b>
(une assertion fausse devient rouge avec son message), des modules
avec <code>children()</code>, du calcul vectoriel, des chaînes et des
littéraux de fonction. Les expressions sur des variables restent des
expressions, donc un programme importé reste paramétrique. Clic droit
&rsaquo; <b>Modificateur de débogage</b> règle <code>#</code>
(surbrillance), <code>%</code> (arrière-plan) ou <code>!</code>
(afficher seulement).</p>
<h3>Bibliothèques</h3>
<p><b>Bibliothèque &rsaquo; Bibliothèques OpenSCAD</b> installe
BOSL2, MCAD, NopSCADlib, Round-Anything, dotSCAD, threads.scad,
Catch'n'Hole et Gridfinity dans votre dossier de bibliothèques
OpenSCAD. Un programme commençant par
<code>include &lt;BOSL2/std.scad&gt;</code> s'ouvre alors ici : les
appels de bibliothèque deviennent des objets quand c'est possible et
restent du code OpenSCAD sinon.</p>
<h3>Personnalisation</h3>
<p>Des commentaires au style Customizer d'OpenSCAD transforment des
variables en contrôles dans l'onglet <b>Variables</b> :</p>
<pre>/* [Size] */
// Box width in mm
width = 40;   // [10:5:200]
lid = "snap"; // [snap, screw, none]</pre>
<p>donne un curseur et une liste déroulante dans la colonne
<i>Ajuster</i>, regroupés et décrits ; les commentaires sont réécrits
lors de l'export.</p>
<h3>Animation</h3>
<p><b>Vue &rsaquo; Animer</b> joue un modèle qui lit <code>$t</code>
(0 à 1) &mdash; <code>rotate([0, 0, 360 * $t])</code> &mdash; et
exporte ses images l'une après l'autre.</p>
"""),

        ("features", "Engrenages, filetages, trous et impression", f"""
<p>Les pièces des bibliothèques OpenSCAD les plus connues sont des
objets dans KherveCAD, chacune avec ses réglages dans Propriétés et un
vrai module OpenSCAD derrière :</p>
<ul>
<li><b>Insertion &rsaquo; Caractéristiques mécaniques</b> :
<b>engrenages</b> à développante (droits, hélicoïdaux, en chevrons,
intérieurs, crémaillère, coniques, à vis sans fin), <b>filetages</b>
(métrique, trapézoïdal, carré, en dents de scie, tuyau, bouteille
&mdash; ou le taraud qui découpe un écrou), <b>trous</b> (lamage,
fraisage, logement d'écrou, insert thermocollé, oblong, en larme),
moletages et surfaces texturées.</li>
<li><b>Insertion &rsaquo; Formes et motifs</b> : polyèdres réguliers,
étoiles, polygones avec un rayon par sommet, formes de Bézier et de
tracé SVG, panneaux en nid d'abeille.</li>
<li><b>Bibliothèque &rsaquo; Impression 3D</b> : queues d'aronde,
clips encastrables, charnières imprimées en place et charnières
souples, bossages d'insert, un bouchon de bouteille fileté, clips de
câble, boîtes et plaques de base Gridfinity, plateaux compartimentés,
un boîtier électronique. <b>Moteurs et électronique</b> : moteurs
NEMA, profilés en T, rails, poulies GT2, roulements, ventilateurs,
cartes Raspberry Pi et Arduino. Aussi le Lego Technic et les panneaux
génératifs.</li>
<li>Clic droit sur une pièce &rsaquo; <b>Séparer pour
l'impression</b> découpe une pièce trop grande pour le plateau en
deux, avec des trous de goujon et une cheville.</li>
</ul>
<p>Deux engrenages s'engrènent quand ils partagent le module et
l'angle de pression et que leurs centres sont distants de m &times;
(z<sub>1</sub> + z<sub>2</sub>) / 2. Pour un écrou, placez un filetage
<i>intérieur</i> dans une Différence avec le corps de l'écrou.</p>
"""),

        ("ai", "Assistants : Claude et le Chat", f"""
<h3>Se connecter à Claude (sans clé API)</h3>
<p><b>IA &rsaquo; Se connecter à Claude (Simple)&hellip;</b> permet à
Claude Desktop, Claude Code, Cursor, Cline, VS Code ou LM Studio de
construire directement dans le document ouvert, avec le compte que
vous avez déjà.</p>
<ol>
<li>Cochez <b>Autoriser les assistants à se connecter à ce
document</b>.</li>
<li>Laissez <b>L'assistant peut</b> sur <b>Complet</b> (recommandé),
pour qu'il puisse aussi ouvrir et exporter les fichiers que vous
mentionnez. <i>Modifier</i> le garde à l'intérieur du document
ouvert ; <i>Lecture seule</i> ne le laisse que regarder.</li>
<li>Sous <b>Connecter une application</b>, choisissez la vôtre et
appuyez sur <b>Connecter</b> ; redémarrez cette application.</li>
<li>Dans sa discussion, <b>mentionnez KherveCAD</b> : par exemple
« <i>dans KherveCAD, construis une équerre de 40 mm avec deux trous
M6</i> ».</li>
</ol>
<p>L'assistant travaille avec de vrais objets : il lit et modifie
l'arbre, écrit de l'OpenSCAD qui arrive sous forme de lignes
modifiables (étiquetées, p. ex. <b>Cube [Body]</b>), insère des
pièces de bibliothèque, assemble des Objets et regarde la vue 3D pour
vérifier son travail. Chacune de ses étapes correspond à un
{K("Ctrl+Z")}. La connexion reste sur cet ordinateur.</p>
<p>L'assistant étiquette chaque pièce qu'il construit (<b>Cube
[Front-left leg]</b>, <b>Sphere [Left eye]</b>), et lorsqu'il fait
d'une pièce un <b>Objet</b> ou un <b>Maître</b>, il vous dit ce qu'il
a fait, pourquoi, et dans quel onglet le trouver.</p>
<h3>Modélisation par instinct</h3>
<p>Vous construisez en conversant ? Cliquez sur <b>Modélisation par
instinct</b> à l'extrémité droite de la barre d'outils principale
({K("Ctrl+Shift+M")}, ou Vue &rsaquo; Modélisation par instinct) :
l'arbre, les Propriétés, l'esquisse 2D et les outils de dessin se
replient, la barre d'outils ne garde que Nouveau, Ouvrir,
Enregistrer, Annuler et Rétablir, et le modèle 3D remplit la fenêtre,
si bien que vous pouvez décrire la pièce et la regarder se
construire. Cliquez de nouveau pour tout ramener et modifier à la
main. Le nom s'inspire du <i>vibe coding</i> &mdash; construire un
logiciel en le décrivant à une IA.</p>
{figure("vibe_model", "Modélisation par instinct : seule la vue 3D "
        "s'affiche, avec sa barre de navigation ; le bouton est "
        "allumé à l'extrémité de la barre d'outils.")}
<h3>Le Chat</h3>
<p><b>IA &rsaquo; Chat</b> {K("Ctrl+/")} ancre un chat à droite qui
fonctionne avec votre propre clé API <b>Claude, Mistral ou
Ollama</b> (le bouton engrenage). Décrivez une pièce, ou collez-en
une image ; la réponse est appliquée au document &mdash; à l'intérieur
de la pièce en cours d'édition quand l'onglet Objet est ouvert. Tapez
<b>/help</b> pour voir ses commandes.</p>
{figure("chat_panel", "Le Chat.", 270)}
"""),

        ("files", "Fichiers, Git et publication", f"""
<ul>
<li><b>.kcad</b> est le format propre à KherveCAD : chaque objet,
couleur, variable, pièce et accrochage. Enregistrer {K("Ctrl+S")},
Enregistrer sous {K("Ctrl+Shift+S")}, Ouvrir {K("Ctrl+O")}, Ouvrir
récent.</li>
<li><b>Ouvrir</b> accepte aussi les programmes .scad et les
maillages (.stl, .obj, .off, .3mf) ; glisser un fichier sur la
fenêtre fonctionne également.</li>
<li><b>Exporter STL</b> {K("Ctrl+Shift+E")} pour l'impression 3D
(exact quand OpenSCAD est installé) ; <b>Exporter OpenSCAD</b>
{K("Ctrl+E")}.</li>
<li><b>Exporter PNG</b> {K("Ctrl+Alt+E")} enregistre une image de la
vue 3D dans ses couleurs, son style et son éclairage : la <b>vue
courante</b> exactement telle que la caméra la montre, ou <b>toutes
les vues standard</b> (l'isométrique des quatre coins, trois quarts
avant, vue plongeante, vue basse et vue du dessous), un fichier
chacune. Choisissez une taille jusqu'à 4K, et cochez <b>Fond
transparent</b> pour déposer l'image sur une diapositive ou une page
web. Votre propre caméra ne bouge jamais.</li>
<li><b>Plan</b> {K("Ctrl+Shift+D")} (aussi dans la barre d'outils)
ouvre le dessin technique 2D du modèle dans sa propre fenêtre. La
première fois, il met en page la feuille tout seul : vues en
troisième angle <b>Face, Dessus et Droite</b> et une isométrique à
la plus grande échelle standard qui convient, les dimensions
globales, le diamètre de chaque trou (<i>3&times; &Oslash;6</i>) avec
son repère de centre, et un <b>cartouche</b> déjà rempli &mdash;
titre, numéro de plan, matériau, la <b>masse</b> calculée à partir du
volume et de la densité du matériau, échelle, format, date et qui l'a
dessiné.
<ul>
<li>Glissez les vues pour les disposer (Dessus et Droite restent
alignées sur Face) ; glissez une cote ou une note par son
étiquette.</li>
<li>Les outils sur la gauche : <b>Cote intelligente</b> {K("D")}
(cliquez un bord rond pour &Oslash; ou R, un bord droit pour sa
longueur, ou deux points &mdash; puis placez-la), cotes horizontale,
verticale, alignée, de diamètre, de rayon et d'angle ; <b>notes</b>
avec lignes de rappel, texte, <b>bulles</b>, repères et lignes de
centre, <b>état de surface</b>, <b>références</b> et
<b>tolérances géométriques</b> ; lignes, rectangles et cercles ; et
<b>vues de détail</b> (une zone agrandie 2:1). Les clics s'accrochent
aux coins, milieux, centres et arêtes.</li>
<li>En haut : Insérer une vue projetée, une <b>coupe</b> hachurée
(sa ligne de coupe dessinée sur la vue qu'elle coupe), une image
ombrée du modèle ou la <b>liste des pièces</b> ; format de feuille
A4&ndash;A0, Letter ou Tabloid ; l'échelle ; <b>papier blanc ou
bleu de plan</b> ; lignes cachées ; cotation automatique ; disposition
automatique.</li>
<li>Sélectionnez n'importe quoi pour le modifier dans
<b>Propriétés</b> &mdash; le texte d'une cote, son préfixe et sa
tolérance &plusmn; ; double-cliquez sur le cartouche pour le
remplir.</li>
<li><b>Exporter en PDF</b>, en <b>DXF</b> (par calques, avec de
vrais types de lignes HIDDEN et CENTER, en millimètres de feuille),
en <b>SVG</b> ou en <b>PNG</b>, ou <b>Imprimer</b>.</li>
</ul>
La feuille est enregistrée dans le .kcad. Après avoir modifié la
pièce, <b>Mettre à jour depuis le modèle</b> {K("F5")} reprojette
chaque vue et conserve vos annotations. Désactivez les lignes
cachées pour les pièces filetées ou très détaillées.</li>
<li><b>Fichier &rsaquo; Afficher dans l'explorateur de fichiers</b>
ouvre le dossier du document ; <b>Nouvelle fenêtre</b>
{K("Ctrl+Shift+N")} ouvre un second document.</li>
<li><b>Vue &rsaquo; Ajouter une image de référence&hellip;</b> place
une photo ou un dessin sur le plan d'esquisse pour le calquer ; elle
s'affiche dans les deux vues.</li>
</ul>
<h3>Git</h3>
<p>Le menu <b>Git</b> versionne le dossier contenant votre document :
<b>Commit</b> {K("Ctrl+K")} enregistre un instantané avec un message,
<b>Pousser</b> / <b>Tirer</b> synchronisent avec GitHub ou GitLab, et
<b>Se connecter à GitHub / GitLab</b> configure le dépôt distant.</p>
<h3>Publier sur Printables</h3>
<p><b>Fichier &rsaquo; Publier sur Printables&hellip;</b>
{K("Ctrl+Shift+P")} prépare tout pour un envoi : fichiers STL et
3MF &mdash; et, pour un assemblage, <b>un STL par Objet</b>
(<code>name-Object.stl</code>, chacun à sa propre origine, prêt à
imprimer séparément ; un Objet à l'intérieur d'une couleur ou d'un
groupe compte aussi, et un placé plusieurs fois n'est écrit qu'une
fois) &mdash; le .scad et le .kcad, une archive source, des images
d'aperçu peintes exactement comme la vue 3D (vos couleurs, matériaux,
éclairage, plateau et ombre) sous huit angles à trois quarts
(l'isométrique avant-droite en premier, comme couverture), une
description et les réponses du formulaire d'envoi. Il ouvre ensuite
la page d'envoi de Printables ; l'envoi final reste à faire en un
clic par vous-même.</p>
"""),

        ("updates", "Mises à jour", f"""
<p>KherveCAD se maintient à jour à partir de ses publications
GitHub.</p>
<ul>
<li>Une copie installée vérifie <b>une fois par jour</b>, quelques
secondes après son démarrage. Quand une version plus récente existe,
une fenêtre liste <b>ce qui a changé</b> : les notes de version et
chaque amélioration depuis votre version.</li>
<li><b>Télécharger et installer</b> la récupère en arrière-plan
(avec une barre de progression annulable), puis ferme KherveCAD,
installe et démarre la nouvelle version. On vous demande d'abord
d'enregistrer le travail non sauvegardé.</li>
<li><b>Ignorer cette version</b> arrête le rappel pour cette version
seulement ; <b>Plus tard</b> redemande la prochaine fois.</li>
<li><b>Aide &rsaquo; Vérifier les mises à jour&hellip;</b> vérifie
maintenant ; <b>Aide &rsaquo; Vérifier les mises à jour
automatiquement</b> active ou désactive la vérification
quotidienne.</li>
</ul>
{figure("dialog_update", "Une mise à jour est disponible : ce qui a "
        "changé, et le choix de l'installer.", 620)}
<p>Le numéro de version est <b>0.1.<i>N</i></b>, où <i>N</i> compte
les modifications apportées à KherveCAD jusqu'ici &mdash; il augmente
de un à chaque changement, et la barre de titre ainsi qu'Aide
&rsaquo; À propos l'affichent.</p>
<p class='tip'>Une copie portable, ou KherveCAD lancé depuis son code
source, n'est pas remplacé automatiquement : la fenêtre de mise à
jour propose alors la page de téléchargement.</p>
"""),

        ("checking", "Vérifier une pièce", f"""
<p>Le menu <b>Analyser</b> (et le menu contextuel de l'arbre)
vérifie une pièce comme le ferait un logiciel de découpe ou de CAO,
avant de l'imprimer ou de l'envoyer. Chaque fenêtre reste ouverte
pendant que vous corrigez ; <b>Vérifier à nouveau</b> relance la
vérification.</p>
<h3>Propriétés de masse</h3>
<p>Volume, surface, taille, centre de masse et boîte englobante des
pièces sélectionnées (ou du document entier), plus la <b>masse</b>
pour un matériau choisi (PLA, PETG, ABS, résine, aluminium,
acier&hellip;), son <b>coût</b> selon votre prix au kilo, et un
temps d'impression <i>approximatif</i>. La masse est celle d'une
pièce pleine ; une impression avec remplissage pèse moins.</p>
<h3>Vérifier pour l'impression 3D</h3>
<p>Quatre vérifications, chacune <span style='color:#2e8b57'>
<b>RÉUSSI</b></span>, <span style='color:#d08a00'>
<b>AVERTISSEMENT</b></span> ou <span style='color:#c0392b'>
<b>ÉCHEC</b></span> :</p>
<ul>
<li><b>Étanche</b> &mdash; la surface est fermée et enroulée de façon
cohérente. Une arête ouverte signifie qu'un logiciel de découpe
pourrait remplir le mauvais côté ou abandonner la pièce ; le rapport
indique où se trouve la première.</li>
<li><b>Surplombs</b> &mdash; les faces orientées vers le bas au-delà
de la limite (45° par défaut) nécessitent des supports. Réorientez la
pièce, ajoutez un chanfrein sous le surplomb, ou acceptez des
supports.</li>
<li><b>Épaisseur de paroi</b> &mdash; les parois plus fines que le
minimum (0,8 mm, deux largeurs d'extrusion) risquent de ne pas
s'imprimer ou de casser. Épaississez-les, ou utilisez une buse plus
fine.</li>
<li><b>Emprise au sol</b> &mdash; une pièce haute sur une petite base
bascule ou se décolle du plateau : posez-la à plat ou ajoutez une
jupe.</li>
</ul>
<p>Cochez <b>Afficher les surplombs et parois fines sur le
modèle</b> pour voir les faces problématiques teintées dans la vue
3D.</p>
{figure("print_check", "Vérification pour l'impression 3D sur une "
        "pièce en T : le dessous du sommet est un surplomb.")}
<h3>Vérifier les interférences</h3>
<p>Deux pièces se chevauchent-elles ? Sélectionnez deux pièces ou
plus (ou aucune, pour chaque pièce de Principal) et chaque paire est
signalée comme <b>sans contact</b>, <b>INTERSECTION</b> (avec un
point de croisement) ou <b>À L'INTÉRIEUR / CONTIENT</b> (l'une se
trouve entièrement dans l'autre). Deux pièces qui ne font que se
toucher sont sans contact. Lancez-le après avoir accroché ou déplacé
des pièces.</p>
<p class='tip'><i>Astuce :</i> ces trois vérifications s'appliquent
au maillage que la vue 3D affiche. Tant que le rendu exact n'est pas
arrivé, une pièce avec une Différence montre ses trous non découpés,
et les résultats le signalent.</p>
"""),

        ("shortcuts", "Raccourcis clavier", f"""
<p>Sur Mac, {K("Ctrl")} correspond à la touche {K("&#8984; Cmd")}.</p>
<table>
<tr><td colspan='2'><b>Outils</b></td></tr>
<tr><td>{K("V")} {K("L")} {K("R")} {K("C")} {K("P")} {K("T")}</td>
<td>Sélectionner, Ligne, Rectangle, Cercle, Polygone, Texte</td></tr>
<tr><td>{K("M")} {K("D")}</td><td>Mesurer, Ajouter une cote</td></tr>
<tr><td>{K("J")}</td><td>Accrocher les objets ensemble</td></tr>
<tr><td>{K("Enter")} / {K("Esc")}</td><td>Terminer / abandonner un
polygone ; {K("Esc")} annule aussi un accrochage</td></tr>
<tr><td colspan='2'><b>Fichier</b></td></tr>
<tr><td>{K("Ctrl+N")} {K("Ctrl+O")} {K("Ctrl+S")}</td><td>Nouveau,
Ouvrir, Enregistrer ({K("Ctrl+Shift+S")} Enregistrer sous,
{K("Ctrl+Shift+N")} Nouvelle fenêtre)</td></tr>
<tr><td>{K("Ctrl+I")} {K("Ctrl+Shift+I")}</td><td>Importer OpenSCAD,
Importer un maillage</td></tr>
<tr><td>{K("Ctrl+E")} {K("Ctrl+Shift+E")}</td><td>Exporter OpenSCAD,
Exporter STL</td></tr>
<tr><td>{K("Ctrl+Alt+E")}</td><td>Exporter PNG</td></tr>
<tr><td>{K("Ctrl+Shift+P")}</td><td>Publier sur Printables</td></tr>
<tr><td colspan='2'><b>Édition</b></td></tr>
<tr><td>{K("Ctrl+Z")} {K("Ctrl+Y")}</td><td>Annuler, Rétablir (aussi
{K("Ctrl+Shift+Z")})</td></tr>
<tr><td>{K("Ctrl+X")} {K("Ctrl+C")} {K("Ctrl+V")}</td><td>Couper,
Copier, Coller</td></tr>
<tr><td>{K("Ctrl+D")} {K("Delete")}</td><td>Dupliquer,
Supprimer</td></tr>
<tr><td>{K("Ctrl+G")} {K("Ctrl+Shift+G")}</td><td>Grouper,
Dégrouper</td></tr>
<tr><td>{K("Ctrl+&uarr;")} {K("Ctrl+&darr;")}</td><td>Monter / descendre
dans l'arbre</td></tr>
<tr><td>{K("Tab")} {K("Shift+Tab")} ({K("A")} {K("Q")})</td><td>Objet
suivant / précédent</td></tr>
<tr><td>{K("Space")}</td><td>Masquer / afficher la sélection</td></tr>
<tr><td colspan='2'><b>Insertion et vue</b></td></tr>
<tr><td>{K("Ctrl+Alt+N")}</td><td>Nouvel objet</td></tr>
<tr><td>{K("Ctrl+L")}</td><td>Bibliothèque de pièces</td></tr>
<tr><td>{K("Ctrl++")} {K("Ctrl+-")} {K("Ctrl+0")}</td><td>Zoom avant,
arrière, réinitialiser l'esquisse</td></tr>
<tr><td>{K("Ctrl+Shift+F")} {K("Ctrl+F")}</td><td>Cadrer l'esquisse,
Cadrer en 3D</td></tr>
<tr><td>{K("Ctrl+'")} {K("Ctrl+Shift+'")}</td><td>Grille, Accrocher à
la grille</td></tr>
<tr><td>{K("F5")}</td><td>Rendre avec OpenSCAD</td></tr>
<tr><td colspan='2'><b>Autres</b></td></tr>
<tr><td>{K("Ctrl+/")}</td><td>Chat</td></tr>
<tr><td>{K("Ctrl+K")}</td><td>Commit Git</td></tr>
<tr><td>{K("F1")}</td><td>Ce guide ({K("Ctrl+F")} pour y
chercher)</td></tr>
</table>
"""),

        ("troubleshooting", "Dépannage", f"""
<h3>Un trou ou une découpe ne s'affiche pas</h3>
<p>L'aperçu instantané dessine une Différence comme son premier
enfant. Attendez que le badge affiche <i>OpenSCAD</i> ou <i>n/n
pièces exactes</i>, ou appuyez sur {K("F5")}. Si la barre d'état
affiche <i>aperçu intégré</i>, OpenSCAD n'a pas été trouvé :
installez-le, ou indiquez son emplacement via <b>Édition &rsaquo;
Localiser OpenSCAD&hellip;</b></p>
<h3>Quelque chose est devenu rouge</h3>
<p>Survolez la ligne rouge : l'info-bulle indique le problème (une
faute de frappe dans une expression, un solide 3D à l'intérieur
d'une extrusion, un profil de révolution qui traverse l'axe&hellip;).
Annulez avec {K("Ctrl+Z")} en cas de doute.</p>
<h3>Une opération n'a rien fait</h3>
<p>Les opérations agissent sur la sélection. Sélectionnez d'abord des
objets &mdash; dans l'onglet Objet, sélectionnez-les dans l'arbre de
<i>cet</i> onglet.</p>
<h3>Le modèle est lent</h3>
<p>Réduisez les <b>Segments communs ($fn)</b> dans l'onglet Principal
(32&ndash;48 suffisent largement pendant la conception), ou les
Segments propres d'une grande forme. Orbiter autour d'un grand modèle
affiche une ébauche plus légère qui revient au détail complet dès que
vous relâchez.</p>
<h3>La vue 3D semble incorrecte</h3>
<p>Appuyez sur <b>Redessiner</b> (&#x27F3;) sur la barre de lumière,
ou sur <b>Cadrer en 3D</b> si le modèle est hors de vue.</p>
<h3>Un assistant ne voit pas KherveCAD</h3>
<p>Vérifiez que <b>Autoriser les assistants à se connecter</b> est
coché dans IA &rsaquo; Se connecter à Claude, que l'application a été
redémarrée après <b>Connecter</b>, et mentionnez KherveCAD dans la
discussion.</p>
<h3>KherveCAD a planté</h3>
<p>Un rapport est écrit dans <code>khervecad_crash.log</code> dans
votre dossier temporaire (<code>%TEMP%</code> sous Windows). Merci de
le joindre en signalant le problème.</p>
"""),
    ]
