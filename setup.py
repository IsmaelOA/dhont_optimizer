from setuptools import setup, find_packages

with open('LICENSE') as f:
    license = f.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='dhont_optimizer',
    version='0.1.0',
    author='Ismael Osuna Ayuste, Alexander Romero Vinogradov',
    author_email='osuna.ismael@gmail.com, aleromvin@gmail.com',
    description="dhont_optimizer is a Python library designed for optimizing seat allocations in electoral systems using the D'Hondt method. It features a flexible configuration that allows for detailed modeling of various provinces and parties, accommodating different political landscapes."
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/IsmaelOA/dhont_optimizer',
    license=license,
    packages=find_packages(),
    install_requires=required,
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)
