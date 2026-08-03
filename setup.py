from setuptools import setup, find_packages

setup(name="dow2-texture-painter",
      version='0.1',
      packages=find_packages(),
      include_package_data=True,
      package_data={
          "src.resources": ["*.ini", "*.json", "*.png", "*.ico"],
      },
      description=("a GUI application to recolor texture from the "
                   "Dawn of War 2 game"),
      entry_points={'console_scripts': [
           'texture-painter = src.frame_main:main']},
      author="Jaccouille",
      author_email='j4ccouille@gmail.com',
      )
