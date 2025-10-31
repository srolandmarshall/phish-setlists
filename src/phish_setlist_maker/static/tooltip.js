/**
 * Track Tooltip Functionality
 * Shows detailed track information from Phish.in API on hover/click
 * Mobile-friendly: click to toggle, tap outside to close
 */

(function () {
  'use strict';

  // Tooltip cache to avoid repeated API calls
  const tooltipCache = new Map();
  let currentTooltip = null;
  let currentLink = null;
  let hideTimeout = null;
  let isTooltipOpen = false;
  
  // Detect if we're on a touch device
  const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

  // Create tooltip element
  function createTooltip() {
    const tooltip = document.createElement('div');
    tooltip.className = 'track-tooltip';
    tooltip.innerHTML = '<div class="track-tooltip-content">Loading...</div>';
    document.body.appendChild(tooltip);
    return tooltip;
  }

  // Format duration from milliseconds
  function formatDuration(ms) {
    if (!ms) return 'Unknown';
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }

  // Fetch track data from Phish.in API
  async function fetchTrackData(trackId) {
    if (tooltipCache.has(trackId)) {
      return tooltipCache.get(trackId);
    }

    try {
      const response = await fetch(
        `https://phish.in/api/v2/tracks/${trackId}.json`
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      tooltipCache.set(trackId, data);
      return data;
    } catch (error) {
      console.error('Failed to fetch track data:', error);
      return null;
    }
  }

  // Render tooltip content
  function renderTooltipContent(data) {
    if (!data) {
      return '<div class="track-tooltip-error">Failed to load track info</div>';
    }

    const {
      title,
      show_date,
      venue_name,
      venue_location,
      likes_count,
      tags = [],
    } = data;

    // Check if there's a jamchart tag
    const jamchartTag = tags.find((tag) => tag.name === 'Jamcharts');
    const jamchartNote = jamchartTag ? jamchartTag.notes : null;

    // Check for teases
    const teases = tags.filter((tag) => tag.name === 'Tease');
    const teasesHtml = teases
      .map((t) => `<div class="tease">🎵 ${t.notes}</div>`)
      .join('');
    
    // Create Phish.in show URL
    const phishinShowUrl = `https://phish.in/${show_date}`;

    const html = `
      <div class="track-tooltip-header">
        <div class="track-title">${title}</div>
      </div>
      <div class="track-tooltip-body">
        <div class="track-show">
          <strong><a href="${phishinShowUrl}" target="_blank" rel="noopener noreferrer">${show_date}</a></strong><br>
          ${venue_name}, ${venue_location}
        </div>
        ${
          jamchartNote
            ? `<div class="jamchart-note">
             <div class="jamchart-badge">⭐ Jamchart</div>
             <div class="jamchart-text">${jamchartNote}</div>
           </div>`
            : ''
        }
        ${teasesHtml}
        <div class="track-stats">
          ❤️ ${likes_count || 0} likes
        </div>
      </div>
    `;

    return html;
  }

  // Position tooltip near the link
  function positionTooltip(tooltip, link) {
    const rect = link.getBoundingClientRect();
    const tooltipRect = tooltip.getBoundingClientRect();
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft =
      window.pageXOffset || document.documentElement.scrollLeft;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // On mobile, position below with full width on small screens
    if (isTouchDevice && viewportWidth < 600) {
      tooltip.style.top = `${rect.bottom + scrollTop + 8}px`;
      tooltip.style.left = '8px';
      tooltip.style.right = '8px';
      tooltip.style.width = 'auto';
      tooltip.style.maxWidth = 'none';
      return;
    }

    // Calculate position (below the link by default)
    let top = rect.bottom + scrollTop + 10;
    let left = rect.left + scrollLeft;

    // Adjust if tooltip would go off the right edge
    if (left + tooltipRect.width > viewportWidth) {
      left = viewportWidth - tooltipRect.width - 10;
    }
    
    // Ensure minimum left margin
    if (left < 10) {
      left = 10;
    }

    // Adjust if tooltip would go off the bottom
    if (top + tooltipRect.height > viewportHeight + scrollTop) {
      top = rect.top + scrollTop - tooltipRect.height - 10;
    }

    tooltip.style.top = `${top}px`;
    tooltip.style.left = `${left}px`;
    tooltip.style.right = 'auto';
    tooltip.style.width = '';
    tooltip.style.maxWidth = '400px';
  }

  // Show tooltip
  async function showTooltip(link) {
    const trackId = link.dataset.trackId;
    if (!trackId) return;

    // Clear any pending hide timeout
    if (hideTimeout) {
      clearTimeout(hideTimeout);
      hideTimeout = null;
    }

    // Create tooltip if it doesn't exist
    if (!currentTooltip) {
      currentTooltip = createTooltip();
    }

    currentLink = link;

    // Show loading state
    currentTooltip.innerHTML =
      '<div class="track-tooltip-content">Loading...</div>';
    currentTooltip.classList.add('visible');
    positionTooltip(currentTooltip, link);

    // Fetch and render data
    const data = await fetchTrackData(trackId);
    if (currentLink === link) {
      // Only update if we're still hovering the same link
      const content = renderTooltipContent(data);
      currentTooltip.innerHTML = `<div class="track-tooltip-content">${content}</div>`;
      positionTooltip(currentTooltip, link);
    }
  }

  // Hide tooltip with delay
  function hideTooltip(immediate = false) {
    if (immediate) {
      if (currentTooltip) {
        currentTooltip.classList.remove('visible');
      }
      currentLink = null;
      isTooltipOpen = false;
      return;
    }
    
    hideTimeout = setTimeout(() => {
      if (currentTooltip) {
        currentTooltip.classList.remove('visible');
      }
      currentLink = null;
      isTooltipOpen = false;
    }, 200); // Small delay to allow moving to tooltip
  }

  // Toggle tooltip (for click behavior)
  async function toggleTooltip(link, event) {
    event.preventDefault();
    event.stopPropagation();
    
    const trackId = link.dataset.trackId;
    if (!trackId) return;

    // If clicking the same link, toggle off
    if (isTooltipOpen && currentLink === link) {
      hideTooltip(true);
      return;
    }

    // Clear any pending hide timeout
    if (hideTimeout) {
      clearTimeout(hideTimeout);
      hideTimeout = null;
    }

    // Create tooltip if it doesn't exist
    if (!currentTooltip) {
      currentTooltip = createTooltip();
    }

    currentLink = link;
    isTooltipOpen = true;

    // Show loading state
    currentTooltip.innerHTML =
      '<div class="track-tooltip-content">Loading...</div>';
    currentTooltip.classList.add('visible');
    positionTooltip(currentTooltip, link);

    // Fetch and render data
    const data = await fetchTrackData(trackId);
    if (currentLink === link) {
      // Only update if we're still showing the same tooltip
      const content = renderTooltipContent(data);
      currentTooltip.innerHTML = `<div class="track-tooltip-content">${content}</div>`;
      positionTooltip(currentTooltip, link);
    }
  }

  // Keep tooltip visible when hovering it
  function setupTooltipHover() {
    if (currentTooltip) {
      currentTooltip.addEventListener('mouseenter', () => {
        if (hideTimeout) {
          clearTimeout(hideTimeout);
          hideTimeout = null;
        }
      });

      currentTooltip.addEventListener('mouseleave', () => {
        hideTooltip();
      });
    }
  }

  // Initialize tooltips
  function initTooltips() {
    const links = document.querySelectorAll('a[data-track-id]');

    links.forEach((link) => {
      // Click handler for both desktop and mobile
      // This must be added with capture=true to run before player.js handler
      link.addEventListener('click', (event) => {
        // Always toggle tooltip, never play audio on first click
        toggleTooltip(link, event);
      }, true); // USE CAPTURE PHASE - runs before player.js

      // Desktop hover behavior (only if not touch device)
      if (!isTouchDevice) {
        link.addEventListener('mouseenter', () => {
          if (!isTooltipOpen) {
            showTooltip(link);
          }
        });

        link.addEventListener('mouseleave', () => {
          if (!isTooltipOpen) {
            hideTooltip();
          }
        });
      }

      // Add a visual indicator that this link has a tooltip
      link.classList.add('has-tooltip');
    });

    setupTooltipHover();
    
    // Close tooltip when clicking outside
    document.addEventListener('click', (event) => {
      if (isTooltipOpen && currentTooltip && currentLink) {
        // Check if click is outside tooltip and link
        const isInsideTooltip = currentTooltip.contains(event.target);
        const isInsideLink = currentLink.contains(event.target);
        
        if (!isInsideTooltip && !isInsideLink) {
          hideTooltip(true);
        }
      }
    });
    
    // Close tooltip on escape key
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && isTooltipOpen) {
        hideTooltip(true);
      }
    });
    
    // Reposition tooltip on window resize
    window.addEventListener('resize', () => {
      if (currentTooltip && currentLink && isTooltipOpen) {
        positionTooltip(currentTooltip, currentLink);
      }
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTooltips);
  } else {
    initTooltips();
  }
  
  // Initialize context toggle for mobile
  function initContextToggle() {
    const contextCard = document.querySelector('.context-card');
    const contextToggle = document.querySelector('.context-toggle');
    
    if (!contextCard || !contextToggle) return;
    
    // Start collapsed on mobile
    if (window.innerWidth <= 768) {
      contextCard.classList.add('collapsed');
    }
    
    contextToggle.addEventListener('click', () => {
      contextCard.classList.toggle('collapsed');
    });
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContextToggle);
  } else {
    initContextToggle();
  }
})();
