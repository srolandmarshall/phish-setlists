// Era picker functionality for Inphinite landing page

document.addEventListener("DOMContentLoaded", () => {
  const useEraFilter = document.getElementById("use-era-filter");
  const eraSelector = document.getElementById("era-selector");
  const eraSelect = document.getElementById("era-select");

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

  function updateGenerateUrl() {
    const params = [];

    if (useEraFilter && useEraFilter.checked && eraSelect && eraSelect.value) {
      params.push(`era=${eraSelect.value}`);
    }

    const useJamControl = document.getElementById("use-jam-control");
    const jamSlider = document.getElementById("jam-slider");

    if (useJamControl && useJamControl.checked && jamSlider) {
      const normalized = (parseInt(jamSlider.value, 10) / 100).toFixed(2);
      params.push(`jamminess=${normalized}`);
    }

    if (params.length > 0) {
      generateBtn.href = `/generate?${params.join("&")}`;
    } else {
      generateBtn.href = "/generate";
    }
  }

  window.updateGenerateUrl = updateGenerateUrl;
  updateGenerateUrl();
});
