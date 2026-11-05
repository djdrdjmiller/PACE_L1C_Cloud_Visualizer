"""Run after generating the explicitly synthetic pair with pace-l1c demo."""
from pace_l1c.scene import Scene
from pace_l1c.render import export

scene=Scene('data/demo/OCI.nc','data/demo/HARP2.nc')
try:
    recipe=scene.default_recipe()
    print(scene.diagnostics(recipe.selected))
    export(scene,recipe,'outputs/synthetic-example')
finally:
    scene.close()
