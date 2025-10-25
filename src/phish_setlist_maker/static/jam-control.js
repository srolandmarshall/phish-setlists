// Jamminess dial functionality for Inphinite landing page

document.addEventListener("DOMContentLoaded", () => {
  const useJamControl = document.getElementById("use-jam-control");
  const jamSelector = document.getElementById("jam-selector");
  const jamSlider = document.getElementById("jam-slider");
  const jamValue = document.getElementById("jam-value");
  const jamWarning = document.getElementById("jam-warning");

  if (!useJamControl || !jamSelector || !jamSlider || !jamValue) {
    return;
  }

  const updateJamDisplay = () => {
    const value = parseInt(jamSlider.value, 10) || 0;
    const normalized = (value / 100).toFixed(2);

    let label = "Balanced";
    if (value < 25) {
      label = "Tight & Tidy";
    } else if (value < 50) {
      label = "Easy Does It";
    } else if (value < 75) {
      label = "Run of the Mill";
    } else if (value < 90) {
      label = "Pretty Jammy";
    } else {
      label = "FULL SEND 🚀";
    }

    jamValue.textContent = `${label} (${normalized})`;

    if (jamWarning) {
      if (normalized > 0.666) {
        jamWarning.textContent =
          "⚠️ Dial at your own risk. Set length and song choice becomes more unstable as this increases.";
        jamWarning.className = "jam-warning jam-warning-high";
        jamWarning.style.display = "block";
      } else if (normalized < 0.333) {
        jamWarning.textContent =
          "😴 Turning this down may result in more songs, but less jams. But expect some weirdness too.";
        jamWarning.className = "jam-warning jam-warning-low";
        jamWarning.style.display = "block";
      } else {
        jamWarning.style.display = "none";
      }
    }

    window.updateGenerateUrl?.();
  };

  useJamControl.addEventListener("change", () => {
    jamSelector.style.display = useJamControl.checked ? "block" : "none";
    window.updateGenerateUrl?.();
  });

  jamSlider.addEventListener("input", updateJamDisplay);

  if (useJamControl.checked) {
    jamSelector.style.display = "block";
  }

  updateJamDisplay();
});
