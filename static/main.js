class Slider {
  constructor(id, onChangeCallback) {
    this.container = document.getElementById(`${id}_sliderContainer`);
    this.handle = document.getElementById(`${id}_sliderHandle`);
    this.isDragging = false;
    this.containerRect = null;
    this.onChangeCallback = onChangeCallback;
    this.suppressCallback = false; // Prevent callback during programmatic updates

    // Ensure container and handle exist
    if (!this.container || !this.handle) {
      throw new Error(`Slider elements for '${id}' not found.`);
    }

    // Bind event listeners
    this.initEvents();
  }

  // Initialize event listeners
  initEvents() {
    const startDrag = (e) => {
      const event = e.touches ? e.touches[0] : e;

      if (event.target === this.handle) {
        this.isDragging = true;
        this.containerRect = this.container.getBoundingClientRect();
        e.preventDefault(); // Prevent scrolling on touch devices
      }
    };

    const stopDrag = () => {
      this.isDragging = false;
    };

    const onDrag = (e) => {
      if (!this.isDragging) return;

      const event = e.touches ? e.touches[0] : e;

      // Calculate the offset inside the container
      let offsetY = event.clientY - this.containerRect.top;

      // Constrain the handle within the track
      if (offsetY < 0) offsetY = 0;
      if (offsetY > this.containerRect.height) offsetY = this.containerRect.height;

      // Move the handle
      this.handle.style.top = offsetY + 'px';

      // Calculate the slider value as a percentage (0–100)
      const percentage = ((this.containerRect.height - offsetY) / this.containerRect.height) * 100;

      // Call the callback function with the updated percentage
      if (this.onChangeCallback && !this.suppressCallback) {
        this.onChangeCallback(Math.round(percentage));
      }

      e.preventDefault(); // Prevent scrolling on touch devices
    };

    // Attach mouse events
    this.handle.addEventListener('mousedown', startDrag);
    document.addEventListener('mouseup', stopDrag);
    document.addEventListener('mousemove', onDrag);

    // Attach touch events
    this.handle.addEventListener('touchstart', startDrag);
    document.addEventListener('touchend', stopDrag);
    document.addEventListener('touchmove', onDrag);
  }

  // Method to set the slider position programmatically
  setSliderPosition(percentage) {
    if (percentage < 0) percentage = 0;
    if (percentage > 100) percentage = 100;

    // Calculate the position based on the percentage
    if (!this.containerRect) {
      this.containerRect = this.container.getBoundingClientRect();
    }
    const offsetY = this.containerRect.height * (1 - percentage / 100);

    // Suppress the callback while updating the position
    this.suppressCallback = true;
    this.handle.style.top = offsetY + 'px';
    this.suppressCallback = false;

    // Optionally, call the callback manually if needed
    if (this.onChangeCallback) {
      this.onChangeCallback(percentage);
    }
  }
}

class Button {
  constructor(id, onChangeCallback) {
    this.button = document.getElementById(`${id}-button`); // Target the button
    this.onChangeCallback = onChangeCallback;

    // Ensure the button exists
    if (!this.button) {
      throw new Error(`Button element for '${id}' not found.`);
    }

    // Bind event listener
    this.initEvents();
  }

  // Initialize event listeners
  initEvents() {
    this.button.addEventListener('click', () => {
      this.toggle(); // Toggle the state
    });
  }

  // Toggle the state of the Button
  toggle() {
    // Call the callback with the updated state
    if (this.onChangeCallback) {
      this.onChangeCallback();
    }
  }

  // Method to set the state programmatically
  setState(isOn) {
    this.button.classList.toggle('on', isOn); // Add/remove 'on' class
  }
}


$(document).ready(function () {

  const socket = io(); 

  let volSlider;
  let brightSlider;

  volSlider = new Slider('vol', (value) => {
    console.log('Volume Slider Value:', value);
    //sliderChanged('vol', value);
  });

  brightSlider = new Slider('bright', (value) => {
    console.log('Brightness Slider Value:', value);
    //sliderChanged('bright', value);
  });

  let micButton;
  let camButton;

  micButton = new Button('mic', () => {
    console.log('Mic Button Toggled');
    buttonToggled('mic');
    micButton.setState(!micButton.button.classList.contains('on'));
  });

  camButton = new Button('cam', () => {
    console.log('Cam Button Toggled');
    buttonToggled('cam');
    camButton.setState(!camButton.button.classList.contains('on'));
  });


  function buttonToggled(buttonId) {
    socket.emit('button-toggle', { id: buttonId });
  }
  function sliderChanged(sliderId, value) {
    socket.emit('slider-change', { id: sliderId, value });
  }

  socket.on('set-button-state', (data) => {
    const { id, state } = data;
    switch (id) {
      case 'mic':
        micButton.setState(state);
        break;
      case 'cam':
        camButton.setState(state);
        break;
    }
  });

  socket.on('set-slider-value', (data) => {
    const { id, value } = data;
    switch (id) {
      case 'vol':
        volSlider.setSliderPosition(value);
        break;
      case 'bright':
        brightSlider.setSliderPosition(value);
        break;
    }
  });

});