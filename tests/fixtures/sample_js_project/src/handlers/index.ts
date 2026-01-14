/** Handler modules. */
export class Handler {
  constructor(private name: string) {}

  handle(): void {
    console.log(`Handling ${this.name}`);
  }
}
