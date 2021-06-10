$(document).ready(function(){
    var settingsBackgroundElement = $("#settings-background");
    var settingsContainerElement = $("#settings-container");
    var settingsButtonElement = $("#settings-button");
    var settingsCloseButtonElement = $("#settings-close-button");

    var radioThemeLight = $("#radio-theme-light");
    var radioThemeDark = $("#radio-theme-dark");
    var radioLabelThemeLight = $("#radio-label-theme-light");
    var radioLabelThemeDark = $("#radio-label-theme-dark");

    function isVisible() {
        return settingsBackgroundElement.css("display") === "flex";
    }

    function toggleSettings(visible) {
        if (visible === undefined) visible = !isVisible();
        settingsBackgroundElement.css("display", visible ? "flex" : "none");
    }

    settingsButtonElement.click(function() {
        toggleSettings();
    });

    settingsBackgroundElement.click(function() {
        toggleSettings();
    });

    settingsContainerElement.click(function(e) {
        e.stopPropagation()
    });

    settingsCloseButtonElement.click(function() {
        toggleSettings();
    });

    // Actual settings below

    radioLabelThemeLight.click(function() {
        setTheme("light");
    });

    radioLabelThemeDark.click(function() {
        setTheme("dark");
    });

    let elemToCheck = getCurrentTheme() === "light" ? radioThemeLight : radioThemeDark;
    elemToCheck.attr("checked", "checked");
});