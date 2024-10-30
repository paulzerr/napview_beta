# <i>napview</i>: real-time sleep scoring and analysis

```napview``` is a powerful and user-friendly software for sleep scoring in the sleep lab. It provides a real-time interface to machine learning tools for sleep data analysis.<br>

## Installation

**1.** Make sure you have [```Python 3.8```](https://www.python.org/downloads/) or later installed on your system. [```pip```](https://pip.pypa.io/en/stable/installation/) and [```venv```](https://docs.python.org/3/library/venv.html) is normally included, otherwise, install manually. <br>


**2.** Create a new virtual environment (venv):

<i>Note: using a virtual environment is not strictly necessary to run napview, but is strongly recommended to ensure compatibility.</i><br>

Open a terminal or command prompt and navigate to the directory where you want to create the venv and run:

    python -m venv napview_venv


<i>Note: This will require approx. 800MB of hard drive space.</i><br>

**3.** Activate the virtual environment:

   macOS and Linux:
     
     source napview_venv/bin/activate

   Windows:

     napview_venv\Scripts\activate

**4.** Clone and install the repository:
   
   ```
   git clone https://github.com/paulzerr/tester2/
   cd tester2
   pip install .
   ```

**5.** Start napview from a terminal or command prompt:
   
   ```
   napview
   ```

**6.** Alternatively start napview by executing the napview.py script.

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

- ```napview``` has been tested with BrainVision EEG amplifiers on Kubuntu 24 Linux and Python 3.12. 

- In principle, any amplifier with real-time streaming capabilities can be used with napview via a [LSL connector script](https://labstreaminglayer.readthedocs.io/info/supported_devices.html). These are available for most EEG amps, or you can create your own.

- Feel free to contact us for assistance to make napview work in your lab setup.


<!-- ## Resources

For detailed tutorials, examples, and additional resources, please refer to the following links:

- [napview Documentation, tutorial and examples](https://napview.readthedocs.io/) -->


<!-- ## Contributing

If you would like to contribute to napview, please refer to our [Contributing Guidelines](https://github.com/napview/napview/blob/main/CONTRIBUTING.md).
 -->

## License

napview is released under the [BSD-3 Clause License](https://github.com/paulzerr/napview_beta/blob/master/LICENSE).


## Contact

If you have any questions, suggestions, or feedback, please feel free to reach out to us:

- Email: paul.zerr [ at ] donders.ru.nl
<!-- - GitHub Issues: [napview/issues](https://github.com/napview/napview/issues) -->

