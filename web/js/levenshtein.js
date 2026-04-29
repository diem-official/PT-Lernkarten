function levenshtein(a, b) {
    var m = a.length, n = b.length;
    var dp = [];
    for (var i = 0; i <= m; i++) {
        dp[i] = [i];
        for (var j = 1; j <= n; j++) {
            dp[i][j] = i === 0 ? j : 0;
        }
    }
    for (var j = 1; j <= n; j++) dp[0][j] = j;

    for (var i = 1; i <= m; i++) {
        for (var j = 1; j <= n; j++) {
            if (a[i - 1] === b[j - 1]) {
                dp[i][j] = dp[i - 1][j - 1];
            } else {
                dp[i][j] = 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
            }
        }
    }
    return dp[m][n];
}

/**
 * Returns 'correct' | 'typo' | 'wrong' | 'empty'.
 * Uses normalised similarity: 1 - dist/max(len_a, len_b)
 * >= 1.0 → correct, >= 0.80 → typo (near miss), < 0.80 → wrong
 */
function getMatchStatus(userInput, solution) {
    var a = userInput.toLowerCase().trim();
    var b = solution.toLowerCase().trim();
    if (a === '') return 'empty';
    if (a === b) return 'correct';
    var dist = levenshtein(a, b);
    var maxLen = Math.max(a.length, b.length);
    var similarity = 1 - dist / maxLen;
    if (similarity >= 0.80) return 'typo';
    return 'wrong';
}
