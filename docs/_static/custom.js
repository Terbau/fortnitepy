function setTheme(themeToSet) {
  localStorage.setItem('theme', themeToSet);
  document.documentElement.setAttribute("data-theme", themeToSet);
}

function getCurrentTheme() {
  return document.documentElement.getAttribute("data-theme");
}

$(document).ready(function () {
  var sections = $('div.section');
  var activeLink = null;
  var bottomHeightThreshold = $(document).height() - 30;

  $(window).scroll(function () {
    var distanceFromTop = $(this).scrollTop();
    var currentSection = null;

    if (distanceFromTop + window.innerHeight > bottomHeightThreshold) {
      currentSection = $(sections[sections.length - 1]);
    }
    else {
      sections.each(function () {
        var section = $(this);
        if (section.offset().top - 1 < distanceFromTop) {
          currentSection = section;
        }
      });
    }

    if (activeLink) {
      activeLink.parent().removeClass('active');
    }

    if (currentSection) {
      activeLink = $('.sphinxsidebar a[href="#' + currentSection.attr('id') + '"]');
      activeLink.parent().addClass('active');
    }
  });

  // Store the fullname of the element clicked for possibly later use.
  $('.source-link').parent().click(function () {
    const rawFullname = $(this).children(":first").attr('class').split(/\s+/).find(function (c) {
      return c.startsWith('fullname')
    });
    if (!rawFullname) return;

    const split = rawFullname.split('-');
    let fullname = split.slice(1, split.length).join('.');

    if (fullname === 'none') fullname = null;
    sessionStorage.setItem('referrer', fullname);
  });

  // Check if a referrer is stored and if so use that value.
  $('.docs-link').click(function () {
    const fullname = sessionStorage.getItem('referrer');
    if (!fullname || fullname === 'null') return;

    const elem = $(this);
    const newHref = elem.attr('href').split('#').slice(0, 1) + '#' + fullname;
    elem.attr('href', newHref);
  });
});

$(document).on('DOMContentLoaded', function () {
  const tables = document.querySelectorAll('.py-attribute-table[data-move-to-id]');
  tables.forEach(function (table) {
    let element = document.getElementById(table.getAttribute('data-move-to-id'));
    let parent = element.parentNode;
    // insert ourselves after the element
    parent.insertBefore(table, element.nextSibling);
  });
});
