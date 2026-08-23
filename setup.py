from setuptools import setup, find_packages
from src.app_identity import APP_VERSION, PACKAGE_NAME

setup(name=PACKAGE_NAME,
      version=APP_VERSION,
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
