// Era picker and Jamminess control functionality for Inphinite landing page

document.addEventListener("DOMContentLoaded", () => {
  const useEraFilter = document.getElementById("use-era-filter");
  const eraSelector = document.getElementById("era-selector");
  const eraSelect = document.getElementById("era-select");

  const useJamControl = document.getElementById("use-jam-control");
  const jamSelector = document.getElementById("jam-selector");
  const jamSlider = document.getElementById("jam-slider");
  const jamValue = document.getElementById("jam-value");

  const generateBtn = document.getElementById("generate-btn");

  if (!generateBtn) {
    return;
  }

  // Toggle era selector visibility
  if (useEraFilter && eraSelector && eraSelect) {
    useEraFilter.addEventListener("change", () => {
      if (useEraFilter.checked) {
        eraSelector.style.display = "block";
      } else {
        eraSelector.style.display = "none";
        eraSelect.value = "";
      }
      updateGenerateUrl();
    });

    eraSelect.addEventListener("change", updateGenerateUrl);
  }

  // Toggle jamminess selector visibility
  if (useJamControl && jamSelector && jamSlider && jamValue) {
    useJamControl.addEventListener("change", () => {
      if (useJamControl.checked) {
        jamSelector.style.display = "block";
      } else {
        jamSelector.style.display = "none";
      }
      updateGenerateUrl();
    });

    // Update jamminess value display and URL
    jamSlider.addEventListener("input", () => {
      const value = parseInt(jamSlider.value);
      const normalized = (value / 100).toFixed(2);

      let label = "Balanced";
      if (value < 25) {
        label = "Tight & Tidy";
      } else if (value < 50) {
        label = "Easy Does It";
      } else if (value < 75) {
        label = "Getting Spacey";
      } else if (value < 90) {
        label = "Pretty Jammy";
      } else {
        label = "FULL SEND 🚀";
      }

      jamValue.textContent = `${label} (${normalized})`;

      // Update warning message based on intensity
      const jamWarning = document.getElementById("jam-warning");
      if (jamWarning) {
        if (normalized > 0.666) {
          // High intensity warning
          jamWarning.textContent =
            "⚠️ Dial at your own risk. Set length and song choice becomes more unstable as this increases.";
          jamWarning.className = "jam-warning jam-warning-high";
          jamWarning.style.display = "block";
        } else if (normalized < 0.333) {
          // Low intensity "warning"
          jamWarning.textContent =
            "😴 Turning this down may result in more songs, but less jams. But expect some weirdness too.";
          jamWarning.className = "jam-warning jam-warning-low";
          jamWarning.style.display = "block";
        } else {
          // Middle range - hide warning
          jamWarning.style.display = "none";
        }
      }

      updateGenerateUrl();
    });
  }

  function updateGenerateUrl() {
    const params = [];

    if (useEraFilter && useEraFilter.checked && eraSelect && eraSelect.value) {
      params.push(`era=${eraSelect.value}`);
    }

    if (useJamControl && useJamControl.checked && jamSlider) {
      const normalized = (parseInt(jamSlider.value) / 100).toFixed(2);
      params.push(`jamminess=${normalized}`);
    }

    if (params.length > 0) {
      generateBtn.href = `/generate?${params.join("&")}`;
    } else {
      generateBtn.href = "/generate";
    }
  }
});
