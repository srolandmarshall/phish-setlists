// Era picker functionality for Inphinite landing page

document.addEventListener('DOMContentLoaded', () => {
  const useEraFilter = document.getElementById('use-era-filter');
  const eraSelector = document.getElementById('era-selector');
  const eraSelect = document.getElementById('era-select');
  const generateBtn = document.getElementById('generate-btn');

  if (!useEraFilter || !eraSelector || !eraSelect || !generateBtn) {
    return;
  }

  // Toggle era selector visibility
  useEraFilter.addEventListener('change', () => {
    if (useEraFilter.checked) {
      eraSelector.style.display = 'block';
    } else {
      eraSelector.style.display = 'none';
      eraSelect.value = '';
    }
    updateGenerateUrl();
  });

  // Update URL when era changes
  eraSelect.addEventListener('change', updateGenerateUrl);

  function updateGenerateUrl() {
    if (useEraFilter.checked && eraSelect.value) {
      generateBtn.href = `/generate?era=${eraSelect.value}`;
    } else {
      generateBtn.href = '/generate';
    }
  }
});
