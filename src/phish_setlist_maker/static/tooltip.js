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
  let isTooltipOpen = false; // Pinned by icon click
  let isHovering = false; // Currently hovering
  
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
  function renderTooltipContent(data, origin) {
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
        ${origin ? `<div class="track-origin">${origin}</div>` : ''}
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
    await showTooltipForLink(link);
  }

  // Hide tooltip with delay
  function hideTooltip(immediate = false) {
    if (immediate) {
      if (currentTooltip) {
        currentTooltip.classList.remove('visible');
      }
      currentLink = null;
      isTooltipOpen = false;
      isHovering = false;
      return;
    }
    
    hideTimeout = setTimeout(() => {
      // Only hide if not hovering and not pinned
      if (!isHovering && !isTooltipOpen) {
        if (currentTooltip) {
          currentTooltip.classList.remove('visible');
        }
        currentLink = null;
      }
    }, 200); // Small delay to allow moving to tooltip
  }

  // Toggle tooltip (for icon click)
  async function toggleTooltip(link, event) {
    const trackId = link.dataset.trackId;
    if (!trackId) return;

    // If tooltip already open for this link, close it
    if (isTooltipOpen && currentLink === link) {
      hideTooltip(true);
      return;
    }

    // Show tooltip and pin it
    await showTooltipForLink(link, true); // true = pin it
  }
  
  // Show tooltip for a link
  async function showTooltipForLink(link, pin = false) {
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
      setupTooltipHover(); // Set up hover handlers on the tooltip itself
    }

    currentLink = link;
    if (pin) {
      isTooltipOpen = true; // Only set if pinning via icon click
    }

    // Show loading state
    currentTooltip.innerHTML =
      '<div class="track-tooltip-content">Loading...</div>';
    currentTooltip.classList.add('visible');
    positionTooltip(currentTooltip, link);

    // Fetch and render data
    const data = await fetchTrackData(trackId);
    if (currentLink === link) {
      // Only update if we're still showing the same tooltip
      const origin = link.dataset.origin || null;
      const content = renderTooltipContent(data, origin);
      currentTooltip.innerHTML = `<div class="track-tooltip-content">${content}</div>`;
      positionTooltip(currentTooltip, link);
    }
  }

  // Keep tooltip visible when hovering it
  function setupTooltipHover() {
    if (currentTooltip) {
      currentTooltip.addEventListener('mouseenter', () => {
        isHovering = true;
        if (hideTimeout) {
          clearTimeout(hideTimeout);
          hideTimeout = null;
        }
      });

      currentTooltip.addEventListener('mouseleave', () => {
        isHovering = false;
        if (!isTooltipOpen) {
          hideTooltip();
        }
      });
    }
  }

  // Initialize tooltips
  function initTooltips() {
    const links = document.querySelectorAll('a[data-track-id]');

    links.forEach((link) => {
      const titleText = link.querySelector('.track-title-text');
      const infoIcon = link.querySelector('.track-info-icon');
      
      if (!titleText || !infoIcon) return;

      // Icon click - show tooltip, prevent song play
      infoIcon.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleTooltip(link, event);
      }, true);

      // Text click - allow normal behavior (play song)
      // Do nothing special, let player.js handle it

      // Desktop hover behavior on text (only if not touch device)
      if (!isTouchDevice) {
        titleText.addEventListener('mouseenter', () => {
          isHovering = true;
          if (!isTooltipOpen) {
            showTooltip(link);
          }
        });

        titleText.addEventListener('mouseleave', () => {
          isHovering = false;
          if (!isTooltipOpen) {
            hideTooltip();
          }
        });
      }
    });
    
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
