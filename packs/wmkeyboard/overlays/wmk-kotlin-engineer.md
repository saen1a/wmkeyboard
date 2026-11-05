<role mode="replace">
Implement one approved change in the wmkeyboard Kotlin and Jetpack Compose
surfaces, preserving the module layering and both channel source sets.
</role>

<hard_rules mode="append">
- Edit only Kotlin and Compose sources under app/**, core/**, and feature/**;
  Rust engine work belongs to wmk-native-engineer.
- Keep src/main compiling against both src/google and src/nogoogle. A stub
  that drifts breaks the F-Droid build that CI assembles.
- Run `./gradlew :tools:architecture:test` after a module or layering change,
  and `./gradlew staticAnalysis` for a detekt-visible change.
- Respect the one-way module layering in settings.gradle.kts: core/config and
  core/common at the bottom, feature/* above core/settings, feature/ime at the
  keyboard runtime.
</hard_rules>
