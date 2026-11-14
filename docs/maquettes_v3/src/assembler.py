# Assemble la maquette : gabarit.html + donnees.json -> ../VoxCX_2.0.html
import pathlib

ici = pathlib.Path(__file__).parent
g = (ici / 'gabarit.html').read_text(encoding='utf-8')
d = (ici / 'donnees.json').read_text(encoding='utf-8')
d = d.replace('�', '').replace('⁠', '')  # caractères invalides venant de certains avis
(ici.parent / 'VoxCX_2.0.html').write_text(g.replace('__DONNEES__', d), encoding='utf-8')
print('ok')
