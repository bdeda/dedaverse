Dedaverse (WIP)
===========================

Dedaverse is an asset system for managing the components of visual media projects, films, and games.

Dedaverse strives to be an easy to install and easy to use system for managing the versioning of assets for your project,
while making it easier for you, the Artists and Producers to focus on the artistic iteration and production status of 
the assets you are creating.

### Contents
- [Art](#focus-on-art-not-on-tech)
- [Production](#production-concerns)
- [Tech](#the-tech)
- [Production Pipeline and Agent Roles](#production-pipeline-and-agent-roles)
- [Getting Started](#getting-started)


## Focus on Art, not on Tech

Development of visual content for various media is developed using standard practices across 
various project types. The Dedaverse helps streamline those standards while making workflows easier 
for artists to iterate on the art, and not be burdened by the technical details of the workflow. 

You will be able to answer these questions quickly and easily:
1. What assets are planned?
2. What assets are in development?
3. What was done today?
4. What do the changes look like?


## Production concerns

Producers and buisiness minded individuals will want to know how much individual assets cost, and if they are 
trending in line with anticipations. Dedaverse helps track time of development for various elements of the assets,
so Producers can accurately and confidently say a set of elements of a certain type costs a certain amount. 

How much did the animations cost on character-x? 
You should be able to see that from the development records for the animation elements of the character asset.


## The Tech

Built with Python, the Dedaverse provides tooling to store and track the development process of an asset from concept to completion. 
Users can brainstorm ideas before committing to an idea for an asset. Once ideas pass through gated checkpoints of developemnt, they 
are transformed into more production-defined models of data for that asset, linking tasks from task management systems like Jira to 
the concrete deliverable of that asset.

The Dedaverse allows the user to configure various plugins for the system to interact with file management and revision management systems. 
One example is our Perforce plugin. This uses Perforce on the back end to handle the versioning and sharing of the project assets, while 
exposing a limited interface to that system as to allow the artists to focus on the artwork, and not be overwhelmed with the technical 
implementation details.


### Extensibility

Dedaverse is driven by plugins that allow you to customize the system for your studio. Plugins can be found and installed via the Plugin Manager. 
The Plugin Manager can be configured to find plugins developed by internal tech teams or third party vendors.  


### Icons

Generic plugin icon from Vecteezy.com


## Production Pipeline and Agent Roles

The [production pipeline guide](docs/pipeline/README.md) describes how a team builds a film or game with 2D and 3D
art: visual development and art bibles, asset construction, rigging, animation, storyboards and previz, VFX,
lighting, audio, and editorial, plus the art skills each step needs.

Dedaverse productions can be run by a mixed team where **a human is the Director/Cinematographer** and **AI agents
perform the other roles**, with a **Producer agent orchestrating** the work
(see [Project Roles](docs/pipeline/08_PROJECT_ROLES.md)). Each agent role is defined by a skill in
[`.github/skills/`](.github/skills/README.md):

| Skill | Role |
|-------|------|
| `producer` | Plans, assigns, tracks, and brings reviews and decisions to the Director |
| `narrative-designer` | Story, script, characters, dialogue |
| `concept-artist` | Designs, art bibles, Visual Bible, color script, pose targets |
| `storyboard-artist` | Storyboards and shot list |
| `previz-artist` | Previz and layout |
| `modeller` | Geometry, UVs, turnarounds |
| `surfacing-lookdev-artist` | Textures, materials, shaders, material library |
| `rigger` | Skeletons, skinning, controls, deformation tests |
| `animator` | Body and facial animation, mocap integration |
| `vfx-artist` | Effects and effects library |
| `lighting-artist` | Shot lighting, compositing, final color |
| `audio-artist` | Dialogue, ambience, effects, music, mix |
| `editor` | The cut and shot frame ranges |

All skills share one set of conventions (approval rules, where work lives in the project, naming, task status,
review packages, and cost recording), documented in [`.github/skills/README.md`](.github/skills/README.md).

As the Director, you can ask the Producer what any asset, shot, or element has cost to build. Every agent records
its measured model usage and machine time in a project cost ledger when the work happens. The Producer records
your review time and external spend. Reports give a money total plus the raw quantities and rates behind it,
with estimates and unpriced items called out. See [Cost Tracking](docs/pipeline/09_COST_TRACKING.md).


## Getting Started

Dedaverse currently runs in Python 3.12 on Windows. 

To check if you have Python 3.12 installed on your machine, open a cmd prompt and run 
```
py --list
```
If there is not an installed version 3.12 or higher (3.13), [install Python 3.12 or higher](https://www.python.org/downloads/)

It is highly recommended that you use a virtual environment for the main Dedaverse application. 
It should be created in a directory that can store several Gb of python package dependencies, as this area will grow as plugins are installed into the system.
```
mkdir D:\dedaverse_app
py -3.12 -m venv D:\dedaverse_app\.venv
```
Next, in the venv, we will pip install Dedaverse from github. This will download and install all of the necessary python dependencies.
```
D:\dedaverse_app\.venv\Scripts\python.exe -m pip install git+https://github.com/bdeda/dedaverse.git
```
Finally, install the startup script that will run Dedaverse when the machine is rebooted.
```
D:\dedaverse_app\.venv\Scripts\python.exe -m dedaverse install
```
You should see a star icon show up in the windows system tray. Click it to get started setting up a new project.
