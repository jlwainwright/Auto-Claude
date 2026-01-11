/** Main entry point. */
import { App } from "./app";
import { config } from "./config";

const app = new App(config);
app.start();

console.log("Application started");
