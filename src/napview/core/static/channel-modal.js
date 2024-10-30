class ChannelModal {
    constructor(id, title, channelsFile) {
        this.id = id;
        this.title = title;
        this.channelsFile = channelsFile;
        this.modal = null;
        this.checkboxes = [];
        this.init();
    }

    init() {
        this.modal = document.createElement('div');
        this.modal.id = this.id;
        this.modal.classList.add('channel-modal');

        const modalContent = document.createElement('div');
        modalContent.classList.add('modal-content');

        const heading = document.createElement('h2');
        heading.textContent = this.title;
        modalContent.appendChild(heading);

        const form = document.createElement('form');
        form.action = '/save-channels';
        form.method = 'POST';
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            this.saveChannels();
        });

        const checkboxContainer = document.createElement('div');
        checkboxContainer.classList.add('checkbox-container');
        form.appendChild(checkboxContainer);

        const saveButton = document.createElement('button');
        saveButton.textContent = 'Save';
        saveButton.type = 'submit';
        form.appendChild(saveButton);

        modalContent.appendChild(form);

        const closeButton = document.createElement('button');
        closeButton.textContent = 'Close';
        closeButton.addEventListener('click', () => {
            this.close();
        });
        modalContent.appendChild(closeButton);

        this.modal.appendChild(modalContent);
        document.body.appendChild(this.modal);

        this.fetchChannels()
            .then(channels => {
                this.createCheckboxes(channels, checkboxContainer);
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }

    fetchChannels() {
        return fetch(this.channelsFile)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.text();
            })
            .then(data => {
                return data.split('\n').filter(channel => channel.trim() !== '');
            })
            .catch(error => {
                console.error('Error fetching channels:', error);
                throw error;
            });
    }

    createCheckboxes(channels, container) {
        channels.forEach(channel => {
            const checkboxWrapper = document.createElement('div');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = channel;
            checkbox.name = 'channels';
            checkbox.value = channel;
            const label = document.createElement('label');
            label.htmlFor = channel;
            label.textContent = channel;
            checkboxWrapper.appendChild(checkbox);
            checkboxWrapper.appendChild(label);
            container.appendChild(checkboxWrapper);
            this.checkboxes.push(checkbox);
        });

        this.updateCheckboxesFromTempFile();
    }

    updateCheckboxesFromTempFile() {
        fetch('/get-selected-channels')
            .then(response => response.json())
            .then(selectedChannels => {
                this.checkboxes.forEach(checkbox => {
                    checkbox.checked = selectedChannels.includes(checkbox.value);
                });
            })
            .catch(error => {
                console.error('Error fetching selected channels:', error);
            });
    }

    saveChannels() {
        const selectedChannels = this.getSelectedChannels();
        console.log('Selected Channels:', selectedChannels);
        
        const formData = new URLSearchParams();
        selectedChannels.forEach(channel => formData.append('channels', channel));
        
        fetch('/save-channels', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData.toString()
        })
        .then(response => response.text())
        .then(data => {
            console.log('Server Response:', data);
            this.close();
        })
        .catch(error => {
            console.error('Error saving channels:', error);
        });
    }

    open() {
        this.modal.style.display = 'block';
        this.updateCheckboxesFromTempFile();
    }


    close() {
        this.modal.style.display = 'none';
    }

    getSelectedChannels() {
        return this.checkboxes
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.value);
    }
}

const modal1 = new ChannelModal('modal1', 'Select Channels 1', "static/channels.txt");
const modal2 = new ChannelModal('modal2', 'Select Channels 2', "static/channels.txt");
const modal3 = new ChannelModal('modal3', 'Select Channels 3', "static/channels.txt");

document.getElementById('openModal1').addEventListener('click', () => {
    modal1.open();
});

document.getElementById('openModal2').addEventListener('click', () => {
    modal2.open();
});

document.getElementById('openModal3').addEventListener('click', () => {
    modal3.open();
});