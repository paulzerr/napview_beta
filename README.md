# napview: real-time sleep scoring and analysis software

```napview``` is a powerful and user-friendly software for real-time sleep scoring in the sleep lab. It provides a real-time interface to machine learning tools for sleep data analysis.

## Installation

**1.** Make sure you have Python 3.8 or later installed on your system. pip and venv is typically included, otherwise, install manually. [Python Downloads](https://www.python.org/downloads/)<br>


**2.** Create a new virtual environment (venv):

   <i>Note: using a virtual environment is not strictly necessary to run napview, but is highly recommended to ensure compatibility.</i><br>

   - Open a terminal or command prompt and navigate to the directory where you want to create the venv and run:
     
     python -m venv napview_venv


<i>Note: This will require approx. 800MB of hard drive space.</i><br>

   - Activate the virtual environment:

   macOS and Linux:

     source napview_venv/bin/activate

   Windows:
     
     napview_venv\Scripts\activate


**3.** Install napview:
   

   pip install napview


**4.** Start napview from a terminal or command prompt:
   

   napview


**5.** Alternatively you can start napview by executing the napview.py script.



## Dependencies

These packages and their dependencies will automatically be installed via pip. Otherwise install manually.

    yasa==0.6.5
    Flask==3.0.3
    peewee==3.17.6
    pylsl==1.16.2
    usleep_api==0.1.3
    setuptools==70.3.0
    edfio==0.4.3


## Compatibility 

- napview has been tested with BrainVision EEG amplifiers.

- In principle, any amplifier with real-time streaming capabilities can be used with napview via a [LSL connector script](https://labstreaminglayer.readthedocs.io/info/supported_devices.html). These are available for most EEG amps, or you can create your own.

- Feel free to contact us for assistance to make napview work in your lab setup.


## Resources

For detailed tutorials, examples, and additional resources, please refer to the following links:

- [napview Documentation, tutorial and examples](https://napview.readthedocs.io/)


## Contributing

If you would like to contribute to napview, please refer to our [Contributing Guidelines](https://github.com/napview/napview/blob/main/CONTRIBUTING.md).


## License

napview is released under the [MIT License](https://github.com/napview/napview/blob/main/LICENSE).


## Contact

If you have any questions, suggestions, or feedback, please feel free to reach out to us:

- Email: paul.zerr [ at ] donders.ru.nl
- GitHub Issues: [napview/issues](https://github.com/napview/napview/issues)

