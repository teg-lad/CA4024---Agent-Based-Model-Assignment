from pathlib import Path
from PIL import Image


def helper(path_object):
    return int(path_object.name.split("_")[0])


simulations = list((Path.cwd() / "Simulations").iterdir())

for sim in simulations:

    # filepaths
    for vac_rate in sim.iterdir():
        agent_plots = sorted(list((vac_rate / "Plots" / "agents").iterdir()), key=helper)

        fp_out = vac_rate / "sim.gif"

        img, *imgs = [Image.open(p) for p in agent_plots]
        img.save(fp=fp_out, format='GIF', append_images=imgs,
                 save_all=True, duration=200, loop=0)
