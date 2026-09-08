import globals from "globals";

export default [
  {
    ignores: [".devcontainer/**", "node_modules/**"],
  },
  {
    files: ["**/*.{js,mjs,cjs}"],
    languageOptions: {
      globals: globals.node,
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "error",
    },
  },
];
