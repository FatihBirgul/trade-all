// Generated native resources only; never edits an installed app or user data.
const { withAndroidStyles, AndroidConfig } = require("expo/config-plugins");
module.exports = (config) =>
  withAndroidStyles(config, (mod) => {
    const items = {
      AppTheme: {
        "android:windowBackground": "@color/splashscreen_background",
        "android:statusBarColor": "@color/splashscreen_background",
        "android:navigationBarColor": "@color/splashscreen_background",
      },
      "Theme.App.SplashScreen": {
        "android:windowLightStatusBar": "false",
        "android:windowLightNavigationBar": "false",
        "android:statusBarColor": "@color/splashscreen_background",
        "android:navigationBarColor": "@color/splashscreen_background",
      },
    };
    for (const [parent, values] of Object.entries(items))
      for (const [name, value] of Object.entries(values))
        mod.modResults = AndroidConfig.Styles.assignStylesValue(
          mod.modResults,
          {
            add: true,
            parent: { name: parent },
            name,
            value,
          },
        );
    return mod;
  });
