.pragma library

// A small arithmetic parser, deliberately not JavaScript eval or a shell.
function calculate(source) {
    try {
        source = source.replace(/^\s*=/, "").replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-")
        if (!source.trim()) return {value: "", error: "Type an expression, for example = 24 * 7"}
        if (source.length > 200) throw new Error("Expression is too long")
        const conversion = source.trim().match(/^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*([a-z°]+[23²³]?)\s+(?:to|in)\s+([a-z°]+[23²³]?)$/i)
        if (conversion) return convert(Number(conversion[1]), conversion[2], conversion[3])
        const tokens = source.match(/(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[()+*/%^-]/g) || []
        if (tokens.join("") !== source.replace(/\s/g, "")) throw new Error("Use numbers, parentheses and + − * / % ^")
        let index = 0, depth = 0
        function checked(value) { if (!Number.isFinite(value) || Math.abs(value) > 1e100) throw new Error("Result is out of range"); return value }
        function atom() {
            if (++depth > 32) throw new Error("Too many nested parentheses")
            let value
            const token = tokens[index++]
            if (token === "(") { value = expression(); if (tokens[index++] !== ")") throw new Error("Close the parentheses") }
            else if (token !== undefined && /^(\d|\.)/.test(token)) value = Number(token)
            else throw new Error("Complete the expression")
            depth--; return checked(value)
        }
        function power() { let value = atom(); if (tokens[index] === "^") { index++; value = checked(Math.pow(value, unary())) } return value }
        function unary() { if (tokens[index] === "+" || tokens[index] === "-") { const sign = tokens[index++]; return (sign === "-" ? -1 : 1) * unary() } return power() }
        function term() {
            let value = unary()
            while (["*", "/", "%"].includes(tokens[index])) {
                const op = tokens[index++], right = unary()
                if ((op === "/" || op === "%") && right === 0) throw new Error("Cannot divide by zero")
                value = checked(op === "*" ? value * right : op === "/" ? value / right : value % right)
            }
            return value
        }
        function expression() {
            let value = term()
            while (tokens[index] === "+" || tokens[index] === "-") { const op = tokens[index++], right = term(); value = checked(op === "+" ? value + right : value - right) }
            return value
        }
        const value = expression()
        if (index !== tokens.length) throw new Error("Check the expression")
        return {value: String(Number(value.toPrecision(12))), error: ""}
    } catch (error) { return {value: "", error: error.message} }
}

// Offline conversions only: dimensions must match. Data units are bytes, not bits.
function convert(value, from, to) {
    const units = {
        mm: ["length", .001], cm: ["length", .01], m: ["length", 1], km: ["length", 1000],
        in: ["length", .0254], inch: ["length", .0254], ft: ["length", .3048], yd: ["length", .9144], mi: ["length", 1609.344],
        mg: ["mass", .001], g: ["mass", 1], kg: ["mass", 1000], oz: ["mass", 28.349523125], lb: ["mass", 453.59237],
        ml: ["volume", .001], l: ["volume", 1], "cm³": ["volume", .001], "m³": ["volume", 1000],
        "mm²": ["area", .000001], "cm²": ["area", .0001], "m²": ["area", 1], "ft²": ["area", .09290304], "in²": ["area", .00064516],
        ms: ["time", .001], s: ["time", 1], sec: ["time", 1], min: ["time", 60], h: ["time", 3600], day: ["time", 86400],
        b: ["data", 1], kb: ["data", 1e3], mb: ["data", 1e6], gb: ["data", 1e9], tb: ["data", 1e12],
        kib: ["data", 1024], mib: ["data", 1048576], gib: ["data", 1073741824], tib: ["data", 1099511627776],
        c: ["temperature", 1, 273.15], f: ["temperature", 5/9, 255.3722222222222], k: ["temperature", 1, 0]
    }
    from = from.toLowerCase().replace("°", "").replace("3", "³").replace("2", "²")
    to = to.toLowerCase().replace("°", "").replace("3", "³").replace("2", "²")
    const left = units[from], right = units[to]
    if (!left || !right) return {value: "", error: "Unknown unit. Try = 25.4 mm to in, = 20 c to f or = 2 gb to mib"}
    if (left[0] !== right[0]) return {value: "", error: "Those units measure different things"}
    const base = value * left[1] + (left[2] || 0)
    if (left[0] === "temperature" && base < -1e-9) return {value: "", error: "Temperature is below absolute zero"}
    let answer = (base - (right[2] || 0)) / right[1]
    if (Math.abs(answer) < 1e-12) answer = 0
    if (!Number.isFinite(answer) || Math.abs(answer) > 1e100) return {value: "", error: "Result is out of range"}
    const suffix = right[0] === "temperature" ? (to === "k" ? "K" : "°" + to.toUpperCase()) : to
    return {value: String(Number(answer.toPrecision(12))) + " " + suffix, error: ""}
}
