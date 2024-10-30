
# <i>napview</i>: real-time sleep scoring and analysis visualizer
### v0.1beta:<br> 
```napview``` is a powerful and user-friendly software for automatic sleep scoring in the sleep lab. It provides a real-time interface to machine learning tools for sleep data analysis.<br>

```napview``` uses machine learning models to infer sleep parameters from incoming EEG data and visualizes the classifier output, quantifying e.g., the probability of a sleep study participant to be in a particular sleep stage. 

```napview``` runs independently of existing lab setups. 



## Installation

**1. Make sure you have [```Python 3.8```](https://www.python.org/downloads/) or later installed on your system.**<br>


**2. Clone the repository:**
   
Open a terminal or command prompt and and run:

   ```
   git clone https://github.com/paulzerr/napview_beta/
   cd napview_beta
   ```

**2.** Create a new virtual environment:

    python3 -m venv napview/napview_venv

<i>Note: using a virtual environment is not strictly necessary to run napview, but is strongly recommended to ensure compatibility. This will require up to 1GB of hard drive space.</i><br>


**3. Activate the virtual environment:**

Navigate to the location where you installed the virtual environment:

   Linux and macOS:
     
     source napview_venv/bin/activate

   Windows:

     napview_venv\Scripts\activate

**4. Install the repository:**
   
   ```
   pip install .
   ```

**5. Start napview**

From a terminal or command prompt:
   
   ```
   napview
   ```

Alternatively:

   ```
   python3 -m napview.py
   ```


## Dependencies

These packages and their dependencies will automatically be installed via pip. Otherwise install manually.

    yasa==0.6.5
    Flask==3.0.3
    peewee==3.17.6
    pylsl==1.16.2
    usleep_api==0.1.3
    setuptools==70.3.0
    edfio==0.4.3


## How to use ```napview```

**1.** Open a command window or terminal, type in ```napview``` and hit Enter. This will open the GUI in your default browser, usually at <a href=http://127.0.0.1:8145>http://127.0.0.1:8145</a>. A folder called "napview" will be created in your user directory. Temporary data, logs and output files will be stored there.

**2.** Select your EEG amplifier as data source. Or you can try out ```napview``` with the built-in EEG simulator, which plays back an .edf file.

**3.** Select your preferred sleep scoring model. U-Sleep is strongly recommended, but requires an API key, which can be requested for free at [https://sleep.ai.ku.dk/](https://sleep.ai.ku.dk/)

**4.** Follow further instructions displayed in red in the Status window on the right (if any).

**5.** When everything is green, click START to begin. A new tab will open with the data visualizers. This will typically be [http://127.0.0.1:8245](http://127.0.0.1:8245). Sleep stage probabilities will be displayed as provided by the classifier, but it will take a few minutes for the scoring to become reliable.

**6.** When you are done, click SHUTDOWN to end the recording and save the data. <br>

 <br>
    


## Compatibility 

- ```napview``` has been tested with BrainVision passive electrode EEG amplifiers on Kubuntu 24 Linux + Windows 10; Python 3.9 + 3.12, but should run on most systems as it is platform independent.

- Any amplifier with real-time streaming capabilities can be used with napview via an [LSL connector script](https://labstreaminglayer.readthedocs.io/info/supported_devices.html). These are available for most EEG amps, or you can create your own with a few lines of Python code.

- Napview runs independently of your lab setup. 

- Feel free to contact us for assistance to make napview work in your lab setup.


## TODO:

- auto-reject bad channels
- 

<!-- ## Resources
For detailed tutorials, examples, and additional resources, please refer to the following links:
- [napview Documentation, tutorial and examples](https://napview.readthedocs.io/) -->


## License

```napview``` is released under the [BSD-3 Clause License](https://github.com/paulzerr/napview_beta/blob/master/LICENSE).


## Contact

If you have any questions, suggestions, or feedback, please feel free to reach out to us:

- Email: paul.zerr [ at ] donders.ru.nl
<!-- - GitHub Issues: [napview/issues](https://github.com/napview/napview/issues) -->

