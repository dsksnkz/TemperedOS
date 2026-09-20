import QtQuick
import QtTest
import "../../.config/quickshell/tempered" as Tempered
import "../../.config/quickshell/tempered-launcher/Calculator.js" as Calculator

Item {
    width: 360; height: 200
    Tempered.FluidSlider { id: slider; width: 300; height: 40; y: 20; modelValue: .5; motionScale: 0 }
    SignalSpy { id: moved; target: slider; signalName: "moved" }
    SignalSpy { id: committed; target: slider; signalName: "committed" }
    TestCase {
        name: "DesktopControls"
        when: windowShown
        function init() { moved.clear(); committed.clear(); slider.modelValue = .5; slider.visualValue = .5 }
        function test_model_update_does_not_write_back() {
            slider.modelValue = .7
            compare(slider.visualValue, .7)
            compare(moved.count, 0); compare(committed.count, 0)
        }
        function test_large_hit_target_and_single_commit() {
            mousePress(slider, 60, 3)
            mouseMove(slider, 240, 3)
            mouseRelease(slider, 240, 3)
            compare(committed.count, 1)
            verify(Math.abs(slider.visualValue - .8) < .01)
            verify(moved.count >= 1)
        }
        function test_external_updates_do_not_fight_drag() {
            mousePress(slider, 210, 20)
            slider.modelValue = .1
            verify(Math.abs(slider.visualValue - .7) < .01)
            mouseRelease(slider, 210, 20)
            compare(committed.count, 1)
        }
        function test_calculator_data() {
            return [
                {tag: "precedence", expression: "= 24 * 7 + 2", result: "170"},
                {tag: "parentheses", expression: "(3+4)/2", result: "3.5"},
                {tag: "negative power", expression: "-2^2", result: "-4"},
                {tag: "negative exponent", expression: "2^-2", result: "0.25"},
                {tag: "right associativity", expression: "2^3^2", result: "512"},
                {tag: "decimal", expression: ".1 + .2", result: "0.3"},
                {tag: "unicode", expression: "6 × 7 − 2", result: "40"}
                ,{tag: "inches", expression: "= 25.4 mm to in", result: "1 in"}
                ,{tag: "temperature", expression: "= 20 c to f", result: "68 °F"}
                ,{tag: "freezing", expression: "= 32 °f to c", result: "0 °C"}
                ,{tag: "storage", expression: "= 1 gib to mib", result: "1024 mib"}
                ,{tag: "mass", expression: "= 1 lb to g", result: "453.59237 g"}
                ,{tag: "time", expression: "= 90 min to h", result: "1.5 h"}
                ,{tag: "volume", expression: "= 1 l to cm³", result: "1000 cm³"}
                ,{tag: "volume ascii", expression: "= 13.6 l to cm3", result: "13600 cm³"}
                ,{tag: "area", expression: "= 1 m2 to cm2", result: "10000 cm²"}
            ]
        }
        function test_calculator(data) { compare(Calculator.calculate(data.expression).value, data.result) }
        function test_reject_unsafe_expressions() {
            for (const expression of ["process.exit()", "1/0", "2 +", "(1+2", "2^999999", "x=5", "2(3)", "= 3 kg to km", "= -5 k to c", "= 5 nonsense to mm"])
                verify(Calculator.calculate(expression).error.length > 0, expression)
        }
    }
}
